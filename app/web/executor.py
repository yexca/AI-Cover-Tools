from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import subprocess
import sys
import threading
import traceback
from collections import defaultdict
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator
from uuid import uuid4

from .formats import AUDIO_EXTENSIONS
from .model_registry import ModelRegistry
from .paths import MODELS_DIR, RUNS_DIR, SEPARATOR_SOURCE_DIR
from .schemas import Workflow
from .workflows import topological_order


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AudioArtifact:
    path: Path
    basename: str
    relative_dir: Path = Path()
    stem: str = "audio"
    model: str = ""
    node: str = ""


@dataclass
class RunState:
    id: str
    workflow_id: str
    status: str = "queued"
    progress: float = 0.0
    message: str = "Queued"
    created_at: str = field(default_factory=_now)
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    outputs: list[str] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    future: Future[Any] | None = field(default=None, repr=False)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "outputs": self.outputs,
        }


class CancelledError(RuntimeError):
    pass


class RunManager:
    """A one-worker queue. GPU models can never execute concurrently."""

    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry
        self._runs: dict[str, RunState] = {}
        self._lock = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audio-web-workflow")

    def submit(self, workflow: Workflow) -> dict[str, Any]:
        run = RunState(id=uuid4().hex, workflow_id=workflow.id)
        with self._lock:
            self._runs[run.id] = run
            self._event(run, "queued", "Workflow queued", progress=0.0)
            run.future = self._pool.submit(self._execute, run, workflow)
        return run.public()

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            run = self._runs.get(run_id)
            return run.public() if run else None

    def cancel(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            run = self._runs.get(run_id)
            if not run:
                return None
            if run.status in {"completed", "failed", "cancelled"}:
                return run.public()
            run.cancel_event.set()
            run.message = "Cancellation requested"
            if run.future and run.future.cancel():
                run.status = "cancelled"
                run.finished_at = _now()
                self._event(run, "cancelled", "Workflow cancelled before it started", progress=run.progress)
            else:
                self._event(run, "cancelling", "Cancellation will take effect after the current model call", progress=run.progress)
            return run.public()

    async def events(self, run_id: str) -> AsyncIterator[str]:
        cursor = 0
        while True:
            with self._lock:
                run = self._runs.get(run_id)
                if not run:
                    yield f"event: error\ndata: {json.dumps({'error': 'Run not found'})}\n\n"
                    return
                pending = run.events[cursor:]
                cursor = len(run.events)
                terminal = run.status in {"completed", "failed", "cancelled"}
            for event in pending:
                # Unnamed SSE messages are consumed by EventSource.onmessage and carry
                # their semantic type inside the JSON payload.
                yield f"id: {event['sequence']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            if terminal and not pending:
                return
            if not pending:
                yield ": keep-alive\n\n"
            await asyncio.sleep(0.35)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _event(self, run: RunState, event_type: str, message: str, **extra: Any) -> None:
        if "progress" in extra:
            run.progress = float(extra["progress"])
        run.message = message
        event = {
            "sequence": len(run.events),
            "type": event_type,
            "run_id": run.id,
            "timestamp": _now(),
            "message": message,
            **extra,
        }
        run.events.append(event)

    def _check_cancel(self, run: RunState) -> None:
        if run.cancel_event.is_set():
            raise CancelledError("Workflow cancelled")

    def _execute(self, run: RunState, workflow: Workflow) -> None:
        try:
            with self._lock:
                run.status = "running"
                run.started_at = _now()
                self._event(run, "started", "Workflow started", progress=0.0)
            output_paths = self._run_workflow(run, workflow)
            self._check_cancel(run)
            with self._lock:
                run.status = "completed"
                run.finished_at = _now()
                run.outputs = [str(path) for path in output_paths]
                self._event(run, "completed", "Workflow completed", progress=1.0, outputs=run.outputs)
        except CancelledError:
            with self._lock:
                run.status = "cancelled"
                run.finished_at = _now()
                self._event(run, "cancelled", "Workflow cancelled", progress=run.progress)
        except Exception as exc:  # task exceptions must be retained for the API
            logging.getLogger("ai_cover.web").exception("Web workflow failed")
            with self._lock:
                run.status = "failed"
                run.finished_at = _now()
                run.error = f"{type(exc).__name__}: {exc}"
                self._event(run, "failed", str(exc), progress=run.progress, error=run.error, traceback=traceback.format_exc())

    def _run_workflow(self, run: RunState, workflow: Workflow) -> list[Path]:
        node_by_id = {node.id: node for node in workflow.nodes}
        incoming = defaultdict(list)
        for edge in workflow.edges:
            incoming[edge.target].append(edge)
        products: dict[tuple[str, str], list[AudioArtifact]] = {}
        final_outputs: list[Path] = []
        order = topological_order(workflow)
        total = max(len(order), 1)
        run_dir = RUNS_DIR / run.id
        run_dir.mkdir(parents=True, exist_ok=True)

        for index, node_id in enumerate(order):
            self._check_cancel(run)
            node = node_by_id[node_id]
            with self._lock:
                self._event(run, "node_started", f"Running {node.type}: {node.id}", node_id=node.id, progress=index / total)
            if node.type in {"input_file", "input_folder"}:
                products[(node.id, "audio")] = self._read_input(node.type, node.data)
            else:
                inputs: list[AudioArtifact] = []
                for edge in incoming[node.id]:
                    handle = edge.source_handle or "audio"
                    inputs.extend(products.get((edge.source, handle), []))
                if node.type == "separator":
                    stems = self._separate(run, node.id, node.data, inputs, run_dir / node.id)
                    for stem, artifacts in stems.items():
                        products[(node.id, stem)] = artifacts
                elif node.type == "output_folder":
                    written = self._write_outputs(run, node.id, node.data, inputs)
                    products[(node.id, "audio")] = [
                        AudioArtifact(path=path, basename=path.stem, node=node.id) for path in written
                    ]
                    final_outputs.extend(written)
            with self._lock:
                self._event(run, "node_completed", f"Finished {node.type}: {node.id}", node_id=node.id, progress=(index + 1) / total)
        return final_outputs

    def _read_input(self, node_type: str, data: dict[str, Any]) -> list[AudioArtifact]:
        path = Path(str(data["path"])).expanduser().resolve()
        if node_type == "input_file":
            if not path.is_file():
                raise FileNotFoundError(f"Input audio file does not exist: {path}")
            if path.suffix.lower() not in AUDIO_EXTENSIONS:
                raise ValueError(f"Unsupported input audio extension: {path.suffix}")
            return [AudioArtifact(path=path, basename=path.stem)]
        if not path.is_dir():
            raise FileNotFoundError(f"Input folder does not exist: {path}")
        recursive = bool(data.get("recursive", True))
        configured = data.get("extensions")
        extensions = {str(ext).lower() if str(ext).startswith(".") else f".{str(ext).lower()}" for ext in configured} if configured else AUDIO_EXTENSIONS
        iterator = path.rglob("*") if recursive else path.glob("*")
        files = sorted(item for item in iterator if item.is_file() and item.suffix.lower() in extensions)
        if not files:
            raise RuntimeError(f"No supported audio files were found in: {path}")
        return [AudioArtifact(path=item, basename=item.stem, relative_dir=item.relative_to(path).parent) for item in files]

    def _separate(
        self,
        run: RunState,
        node_id: str,
        data: dict[str, Any],
        inputs: list[AudioArtifact],
        output_dir: Path,
    ) -> dict[str, list[AudioArtifact]]:
        if not inputs:
            return {}
        source_text = str(SEPARATOR_SOURCE_DIR.resolve())
        if source_text not in sys.path:
            sys.path.insert(0, source_text)
        from audio_separator.separator import Separator

        filename = str(data.get("model_filename") or data["model"])
        model = self.registry.find(filename) or {}
        expected = [str(value) for value in model.get("outputs") or data.get("outputs") or []]
        output_dir.mkdir(parents=True, exist_ok=True)
        from app.config import defaults

        common = dict(defaults.COMMON_SEPARATOR_OPTIONS)
        common.update(data.get("options") or {})
        allowed_common = {
            "output_format", "output_bitrate", "normalization_threshold", "amplification_threshold",
            "invert_using_spec", "sample_rate", "use_soundfile", "use_autocast", "use_directml", "chunk_duration",
        }
        common = {key: value for key, value in common.items() if key in allowed_common}
        def merged(default_values: dict[str, Any], key: str) -> dict[str, Any]:
            values = dict(default_values)
            values.update(data.get(key) or {})
            return values

        separator = Separator(
            log_level=logging.INFO,
            model_file_dir=str(MODELS_DIR),
            output_dir=str(output_dir),
            mdx_params=merged(defaults.DEFAULT_MDX_PARAMS, "mdx_params"),
            vr_params=merged(defaults.DEFAULT_VR_PARAMS, "vr_params"),
            demucs_params=merged(defaults.DEFAULT_DEMUCS_PARAMS, "demucs_params"),
            mdxc_params=merged(defaults.DEFAULT_MDXC_PARAMS, "mdxc_params"),
            **common,
        )
        separator.load_model(model_filename=filename)
        result: dict[str, list[AudioArtifact]] = defaultdict(list)
        for item_index, artifact in enumerate(inputs):
            self._check_cancel(run)
            prefix = re.sub(r"[^a-zA-Z0-9_-]+", "_", f"{artifact.basename}_{node_id}_{item_index}")
            custom_names = {stem: f"{prefix}__{stem}" for stem in expected}
            paths = separator.separate(str(artifact.path), custom_output_names=custom_names or None)
            for raw_path in paths:
                output_path = Path(raw_path)
                if not output_path.is_absolute():
                    output_path = output_dir / output_path
                stem = self._identify_stem(output_path, prefix, expected)
                result[stem].append(
                    AudioArtifact(
                        path=output_path,
                        basename=artifact.basename,
                        relative_dir=artifact.relative_dir,
                        stem=stem,
                        model=Path(filename).stem,
                        node=node_id,
                    )
                )
            with self._lock:
                self._event(
                    run,
                    "file_completed",
                    f"Separated {artifact.path.name}",
                    node_id=node_id,
                    file=str(artifact.path),
                    file_index=item_index + 1,
                    file_count=len(inputs),
                    progress=run.progress,
                )
        return dict(result)

    @staticmethod
    def _identify_stem(path: Path, prefix: str, expected: list[str]) -> str:
        name = path.stem.lower()
        for stem in expected:
            if name == f"{prefix}__{stem}".lower() or f"__{stem.lower()}" in name:
                return stem
        match = re.search(r"\(([^)]+)\)", path.stem)
        if match:
            return match.group(1)
        for stem in expected:
            if stem.lower() in name:
                return stem
        return expected[0] if len(expected) == 1 else "unknown"

    def _write_outputs(self, run: RunState, node_id: str, data: dict[str, Any], inputs: list[AudioArtifact]) -> list[Path]:
        output_root = Path(str(data["path"])).expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        template = str(data.get("naming_template") or "{relative_dir}/{basename}_{stem}.{ext}")
        conflict = str(data.get("conflict") or "rename")
        requested_format = str(data.get("format") or "same").lower().lstrip(".")
        written: list[Path] = []
        for artifact in inputs:
            self._check_cancel(run)
            relative_dir = "" if artifact.relative_dir == Path() else artifact.relative_dir.as_posix()
            source_extension = artifact.path.suffix.lower().lstrip(".")
            destination_extension = source_extension if requested_format in {"", "same", "source"} else requested_format
            relative_name = template.format(
                relative_dir=relative_dir,
                basename=artifact.basename,
                stem=artifact.stem,
                ext=destination_extension,
                model=artifact.model,
                node=artifact.node or node_id,
            ).replace("//", "/").lstrip("/\\")
            relative_path = Path(relative_name)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise ValueError(f"Output naming template escapes the selected folder: {relative_name}")
            destination = output_root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if conflict == "skip":
                    continue
                if conflict != "overwrite":
                    destination = self._unique_path(destination)
            if destination_extension == source_extension:
                shutil.copy2(artifact.path, destination)
            else:
                ffmpeg = shutil.which("ffmpeg")
                if not ffmpeg:
                    raise RuntimeError(f"ffmpeg is required to convert {source_extension} to {destination_extension}")
                completed = subprocess.run(
                    [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(artifact.path), "-vn", str(destination)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if completed.returncode != 0:
                    raise RuntimeError(f"ffmpeg conversion failed for {artifact.path.name}: {completed.stderr.strip()}")
            written.append(destination)
        return written

    @staticmethod
    def _unique_path(path: Path) -> Path:
        index = 2
        candidate = path
        while candidate.exists():
            candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
            index += 1
        return candidate
