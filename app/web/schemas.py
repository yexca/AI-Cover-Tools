from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowNode(BaseModel):
    id: str
    type: Literal["input_file", "input_folder", "separator", "output_folder"]
    data: dict[str, Any] = Field(default_factory=dict)
    position: dict[str, float] | None = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value: Any) -> Any:
        return {
            "file_input": "input_file",
            "folder_input": "input_folder",
            "output": "output_folder",
            "model": "separator",
        }.get(value, value)

    @model_validator(mode="after")
    def flatten_editor_config(self) -> "WorkflowNode":
        config = self.data.get("config")
        if not isinstance(config, dict):
            return self
        if self.type in {"input_file", "input_folder"}:
            self.data.setdefault("path", config.get("path"))
            self.data.setdefault("recursive", config.get("recursive", True))
            include = config.get("include")
            if include and "extensions" not in self.data:
                self.data["extensions"] = [part.strip().replace("*", "") for part in str(include).split(";") if part.strip()]
        elif self.type == "output_folder":
            self.data.setdefault("path", config.get("path"))
            self.data.setdefault("naming_template", config.get("naming") or config.get("naming_template"))
            self.data.setdefault("conflict", config.get("conflict", "rename"))
            self.data.setdefault("format", config.get("format", "same"))
        elif self.type == "separator":
            options = self.data.setdefault("options", {})
            if config.get("output_format"):
                options.setdefault("output_format", str(config["output_format"]).upper())
        return self


class WorkflowEdge(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    source: str
    target: str
    source_handle: str | None = None
    target_handle: str | None = None


class Workflow(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str = "Untitled workflow"
    version: int = 1
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    updated_at: str = Field(default_factory=utc_now)


class RefreshRequest(BaseModel):
    scope: Literal["local", "catalog", "all"] = "local"
    force: bool = False


class RunRequest(BaseModel):
    workflow_id: str | None = None
    workflow: Workflow | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_bare_workflow(cls, value: Any) -> Any:
        if isinstance(value, dict) and "nodes" in value and "workflow" not in value:
            return {"workflow": value}
        return value
