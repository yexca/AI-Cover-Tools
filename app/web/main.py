from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .executor import RunManager
from .dialogs import DialogBusyError, DialogError, DialogRequest, is_loopback_client, pick_path
from .model_registry import ModelRegistry
from .paths import STATIC_DIR
from .schemas import RefreshRequest, RunRequest, Workflow
from .workflows import WorkflowStore, validate_workflow_detailed


def create_app(
    registry: ModelRegistry | None = None,
    workflow_store: WorkflowStore | None = None,
    run_manager: RunManager | None = None,
) -> FastAPI:
    model_registry = registry or ModelRegistry()
    workflows = workflow_store or WorkflowStore()
    runs = run_manager or RunManager(model_registry)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # Never block first paint and never access the network here.
        refresh_task = asyncio.create_task(asyncio.to_thread(model_registry.refresh, "local", False))
        yield
        if not refresh_task.done():
            refresh_task.cancel()
        runs.shutdown()

    app = FastAPI(title="AI Cover Audio Workflow API", version="0.1.0", lifespan=lifespan)
    app.state.model_registry = model_registry
    app.state.workflow_store = workflows
    app.state.run_manager = runs

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "service": "ai-cover-webui", "version": app.version}

    @app.get("/api/models")
    def get_models(
        installed: bool | None = Query(default=None),
        function: str | None = Query(default=None),
        architecture: str | None = Query(default=None),
    ) -> dict[str, Any]:
        snapshot = model_registry.snapshot()
        values = snapshot.get("models", [])
        if installed is not None:
            values = [model for model in values if bool(model.get("installed")) == installed]
        if function:
            values = [model for model in values if model.get("function") == function]
        if architecture:
            values = [model for model in values if str(model.get("architecture", "")).lower() == architecture.lower()]
        return {**snapshot, "models": values, "filtered_total": len(values)}

    @app.post("/api/models/refresh")
    async def refresh_models(payload: RefreshRequest) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(model_registry.refresh, payload.scope, payload.force)
        except Exception as exc:
            raise HTTPException(status_code=502 if payload.scope != "local" else 500, detail=str(exc)) from exc

    @app.post("/api/dialog/pick")
    async def pick_local_path(payload: DialogRequest, request: Request) -> Any:
        client_host = request.client.host if request.client else None
        if not is_loopback_client(client_host):
            return JSONResponse(
                status_code=403,
                content={
                    "path": None,
                    "cancelled": False,
                    "error": {"code": "loopback_required", "message": "Native path dialogs are only available to local clients."},
                },
            )
        try:
            return await asyncio.to_thread(pick_path, payload.kind, payload.initial_path, payload.locale)
        except DialogBusyError as exc:
            return JSONResponse(
                status_code=409,
                content={"path": None, "cancelled": False, "error": {"code": exc.code, "message": str(exc)}},
            )
        except DialogError as exc:
            return JSONResponse(
                status_code=400 if exc.code == "unsupported_audio_file" else 500,
                content={"path": None, "cancelled": False, "error": {"code": exc.code, "message": str(exc)}},
            )
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={
                    "path": None,
                    "cancelled": False,
                    "error": {"code": "dialog_failed", "message": str(exc) or "Unable to open the native path dialog."},
                },
            )

    @app.get("/api/workflows")
    def list_workflows() -> dict[str, Any]:
        values = workflows.list()
        return {"workflows": values, "total": len(values)}

    @app.post("/api/workflows", status_code=status.HTTP_201_CREATED)
    def create_workflow(workflow: Workflow) -> Workflow:
        return workflows.save(workflow)

    @app.get("/api/workflows/{workflow_id}")
    def get_workflow(workflow_id: str) -> Workflow:
        workflow = workflows.get(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return workflow

    @app.put("/api/workflows/{workflow_id}")
    def update_workflow(workflow_id: str, workflow: Workflow) -> Workflow:
        workflow.id = workflow_id
        return workflows.save(workflow)

    @app.delete("/api/workflows/{workflow_id}")
    def delete_workflow(workflow_id: str) -> dict[str, bool]:
        if not workflows.delete(workflow_id):
            raise HTTPException(status_code=404, detail="Workflow not found")
        return {"deleted": True}

    @app.post("/api/workflows/validate")
    def validate(workflow: Workflow) -> dict[str, Any]:
        return validate_workflow_detailed(workflow, model_registry)

    @app.get("/api/runs")
    def list_runs(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
        values = runs.list(limit=limit)
        return {"runs": values, "total": len(values)}

    @app.post("/api/runs", status_code=status.HTTP_202_ACCEPTED)
    def create_run(payload: RunRequest) -> dict[str, Any]:
        workflow = payload.workflow
        if not workflow and payload.workflow_id:
            workflow = workflows.get(payload.workflow_id)
        if not workflow:
            raise HTTPException(status_code=400, detail="Provide workflow or workflow_id")
        validation = validate_workflow_detailed(workflow, model_registry)
        if not validation["valid"]:
            raise HTTPException(status_code=422, detail={"message": "Workflow validation failed", **validation})
        return runs.submit(workflow)

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        value = runs.get(run_id)
        if not value:
            raise HTTPException(status_code=404, detail="Run not found")
        return value

    @app.delete("/api/runs/{run_id}")
    def cancel_run(run_id: str) -> dict[str, Any]:
        value = runs.cancel(run_id)
        if not value:
            raise HTTPException(status_code=404, detail="Run not found")
        return value

    @app.get("/api/runs/{run_id}/events")
    async def run_events(run_id: str, request: Request) -> StreamingResponse:
        if not runs.get(run_id):
            raise HTTPException(status_code=404, detail="Run not found")

        async def stream():
            async for event in runs.events(run_id):
                if await request.is_disconnected():
                    break
                yield event

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # The frontend can be built into app/web/static without changing API code.
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

        @app.get("/", include_in_schema=False)
        def web_index() -> FileResponse:
            index = STATIC_DIR / "index.html"
            if not index.exists():
                raise HTTPException(status_code=404, detail="WebUI frontend has not been built")
            return FileResponse(index)

        @app.get("/{path:path}", include_in_schema=False)
        def web_fallback(path: str) -> FileResponse:
            if path.startswith("api/"):
                raise HTTPException(status_code=404, detail="API endpoint not found")
            requested = (STATIC_DIR / path).resolve()
            if requested.is_file() and STATIC_DIR.resolve() in requested.parents:
                return FileResponse(requested)
            index = STATIC_DIR / "index.html"
            if index.exists():
                return FileResponse(index)
            raise HTTPException(status_code=404, detail="Not found")

    return app


app = create_app()
