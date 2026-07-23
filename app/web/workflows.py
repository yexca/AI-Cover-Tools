from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict, deque
from hashlib import sha256
from pathlib import Path
from threading import RLock
from typing import Any

from .formats import AUDIO_EXTENSIONS
from .model_registry import ModelRegistry
from .paths import LEGACY_WORKFLOWS_PATH, WORKFLOWS_DIR
from .schemas import Workflow, utc_now


class WorkflowValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


class WorkflowConflictError(RuntimeError):
    pass


class WorkflowNotFoundError(LookupError):
    pass


class WorkflowStore:
    def __init__(self, path: Path = WORKFLOWS_DIR, legacy_path: Path | None = None) -> None:
        if path.suffix.lower() == ".json":
            self.directory = path.with_suffix("")
            self.legacy_path = path
        else:
            self.directory = path
            self.legacy_path = legacy_path if legacy_path is not None else (
                LEGACY_WORKFLOWS_PATH if path == WORKFLOWS_DIR else None
            )
        self.path = self.directory
        self._lock = RLock()
        self._migrate_legacy()

    @staticmethod
    def _filename(workflow_id: str) -> str:
        return f"{sha256(workflow_id.encode('utf-8')).hexdigest()}.json"

    def _workflow_path(self, workflow_id: str) -> Path:
        return self.directory / self._filename(workflow_id)

    @staticmethod
    def _read_path(path: Path) -> dict[str, Any] | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except (OSError, ValueError):
            return None

    @staticmethod
    def _write_path(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(value, stream, indent=2, ensure_ascii=False)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _migrate_legacy(self) -> None:
        if self.legacy_path is None or not self.legacy_path.is_file():
            return
        marker = self.directory / ".legacy-migrated"
        if marker.exists():
            return
        with self._lock:
            if marker.exists():
                return
            legacy = self._read_path(self.legacy_path)
            if legacy is None:
                return
            self.directory.mkdir(parents=True, exist_ok=True)
            for value in legacy.values():
                try:
                    workflow = Workflow.model_validate(value)
                except (TypeError, ValueError):
                    continue
                target = self._workflow_path(workflow.id)
                if not target.exists():
                    if workflow.revision < 1:
                        workflow.revision = 1
                    self._write_path(target, workflow.model_dump(mode="json"))
            self._write_path(marker, {"migrated": True})

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            values: list[Workflow] = []
            if self.directory.exists():
                for path in self.directory.glob("*.json"):
                    raw = self._read_path(path)
                    if raw is None:
                        continue
                    try:
                        values.append(Workflow.model_validate(raw))
                    except ValueError:
                        continue
            return sorted(
                (
                    {
                        "id": workflow.id,
                        "name": workflow.name,
                        "revision": workflow.revision,
                        "updated_at": workflow.updated_at,
                    }
                    for workflow in values
                ),
                key=lambda item: item["updated_at"],
                reverse=True,
            )

    def get(self, workflow_id: str) -> Workflow | None:
        with self._lock:
            value = self._read_path(self._workflow_path(workflow_id))
        if value is None or value.get("id") != workflow_id:
            return None
        try:
            return Workflow.model_validate(value)
        except ValueError:
            return None

    def create(self, workflow: Workflow) -> Workflow:
        with self._lock:
            target = self._workflow_path(workflow.id)
            if target.exists():
                raise WorkflowConflictError(f"Workflow '{workflow.id}' already exists")
            workflow.updated_at = utc_now()
            workflow.revision = 1
            self._write_path(target, workflow.model_dump(mode="json"))
        return workflow

    def update(self, workflow_id: str, workflow: Workflow) -> Workflow:
        with self._lock:
            target = self._workflow_path(workflow_id)
            stored_raw = self._read_path(target)
            if stored_raw is None or stored_raw.get("id") != workflow_id:
                raise WorkflowNotFoundError(f"Workflow '{workflow_id}' was not found")
            stored = Workflow.model_validate(stored_raw)
            if workflow.revision != stored.revision:
                raise WorkflowConflictError(
                    f"Workflow '{workflow_id}' changed on disk (expected revision {workflow.revision}, current {stored.revision})"
                )
            workflow.id = workflow_id
            workflow.updated_at = utc_now()
            workflow.revision = stored.revision + 1
            self._write_path(target, workflow.model_dump(mode="json"))
        return workflow

    def save(self, workflow: Workflow) -> Workflow:
        stored = self.get(workflow.id)
        if stored is None:
            return self.create(workflow)
        workflow.revision = stored.revision
        return self.update(workflow.id, workflow)

    def delete(self, workflow_id: str) -> bool:
        with self._lock:
            target = self._workflow_path(workflow_id)
            value = self._read_path(target)
            if value is None or value.get("id") != workflow_id:
                return False
            target.unlink()
            return True


def validate_workflow_detailed(workflow: Workflow, registry: ModelRegistry) -> dict[str, Any]:
    errors: list[str] = []
    global_errors: list[str] = []
    node_errors: dict[str, list[str]] = defaultdict(list)
    edge_errors: dict[str, list[str]] = defaultdict(list)

    def add_global(message: str) -> None:
        errors.append(message)
        global_errors.append(message)

    def add_node(node_id: str, message: str) -> None:
        errors.append(message)
        node_errors[node_id].append(message)

    def add_edge(edge_id: str, message: str) -> None:
        errors.append(message)
        edge_errors[edge_id].append(message)

    node_by_id = {node.id: node for node in workflow.nodes}
    if len(node_by_id) != len(workflow.nodes):
        add_global("Node IDs must be unique")
    if not workflow.nodes:
        add_global("Workflow has no nodes")
    incoming: dict[str, list[str]] = defaultdict(list)
    outgoing: dict[str, list[str]] = defaultdict(list)
    edge_ids = {edge.id for edge in workflow.edges}
    if len(edge_ids) != len(workflow.edges):
        add_global("Edge IDs must be unique")
    for edge in workflow.edges:
        source = node_by_id.get(edge.source)
        target = node_by_id.get(edge.target)
        if source is None:
            add_edge(edge.id, f"Edge {edge.id} has an unknown source node: {edge.source}")
        if target is None:
            add_edge(edge.id, f"Edge {edge.id} has an unknown target node: {edge.target}")
        if source is None or target is None:
            continue
        if edge.source == edge.target:
            add_edge(edge.id, f"Node {edge.source} cannot connect to itself")
        incoming[edge.target].append(edge.source)
        outgoing[edge.source].append(edge.target)

        source_type = source.type
        target_type = target.type
        if source_type == "output_folder":
            add_edge(edge.id, f"Output node {edge.source} cannot have outgoing edges")
        if target_type in {"input_file", "input_folder"}:
            add_edge(edge.id, f"Input node {edge.target} cannot have incoming edges")
        source_handle = edge.source_handle or "audio"
        target_handle = edge.target_handle or "audio"
        if source_type in {"input_file", "input_folder"} and source_handle != "audio":
            add_edge(edge.id, f"Input node {edge.source} has no output port: {source_handle}")
        if target_type in {"separator", "output_folder"} and target_handle != "audio":
            add_edge(edge.id, f"Node {edge.target} has no input port: {target_handle}")

    for node in workflow.nodes:
        data = node.data
        if node.type == "input_file":
            if not data.get("path"):
                add_node(node.id, f"Input file node {node.id} is missing path")
            else:
                path = Path(str(data["path"])).expanduser()
                if not path.exists():
                    add_node(node.id, f"Input audio file does not exist: {path}")
                elif not path.is_file():
                    add_node(node.id, f"Input audio path is not a file: {path}")
                elif path.suffix.lower() not in AUDIO_EXTENSIONS:
                    add_node(node.id, f"Unsupported input audio extension: {path.suffix}")
        elif node.type == "input_folder":
            if not data.get("path"):
                add_node(node.id, f"Input folder node {node.id} is missing path")
            else:
                path = Path(str(data["path"])).expanduser()
                if not path.exists():
                    add_node(node.id, f"Input folder does not exist: {path}")
                elif not path.is_dir():
                    add_node(node.id, f"Input folder path is not a directory: {path}")
        elif node.type == "separator":
            filename = data.get("model_filename") or data.get("model")
            if not filename:
                add_node(node.id, f"Separator node {node.id} is missing model_filename")
            else:
                model = registry.find(str(filename))
                if not model:
                    add_node(node.id, f"Separator node {node.id} uses an unknown model: {filename}")
                elif not model.get("installed"):
                    add_node(node.id, f"Separator model is not installed: {filename}")
                output_names = set(model.get("outputs") or []) if model else set()
                if model and model.get("installed") and not output_names:
                    add_node(node.id, f"Separator model output stems are unknown: {filename}")
                for edge in workflow.edges:
                    if edge.source == node.id:
                        source_handle = edge.source_handle or "audio"
                        if output_names and source_handle not in output_names:
                            add_edge(edge.id, f"Separator node {node.id} has no output stem: {source_handle}")
            if not incoming[node.id]:
                add_node(node.id, f"Separator node {node.id} has no audio input")
        elif node.type == "output_folder":
            if not data.get("path"):
                add_node(node.id, f"Output node {node.id} is missing path")
            else:
                path = Path(str(data["path"])).expanduser()
                if path.exists() and not path.is_dir():
                    add_node(node.id, f"Output path is not a directory: {path}")
            if not incoming[node.id]:
                add_node(node.id, f"Output node {node.id} has no audio input")

    if not any(node.type in {"input_file", "input_folder"} for node in workflow.nodes):
        add_global("Workflow needs at least one input node")
    if not any(node.type == "output_folder" for node in workflow.nodes):
        add_global("Workflow needs at least one output node")

    indegree = {node.id: 0 for node in workflow.nodes}
    for targets in outgoing.values():
        for target in targets:
            indegree[target] += 1
    queue = deque(node for node, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        source = queue.popleft()
        visited += 1
        for target in outgoing[source]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(workflow.nodes):
        add_global("Workflow contains a cycle")
        for node_id, degree in indegree.items():
            if degree > 0:
                add_node(node_id, "Node participates in a workflow cycle")
    return {
        "valid": not errors,
        "errors": errors,
        "global_errors": global_errors,
        "node_errors": dict(node_errors),
        "edge_errors": dict(edge_errors),
    }


def validate_workflow(workflow: Workflow, registry: ModelRegistry) -> list[str]:
    """Compatibility helper for callers that only need flat messages."""

    return validate_workflow_detailed(workflow, registry)["errors"]


def topological_order(workflow: Workflow) -> list[str]:
    indegree = {node.id: 0 for node in workflow.nodes}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in workflow.edges:
        outgoing[edge.source].append(edge.target)
        indegree[edge.target] += 1
    queue = deque(node_id for node_id, degree in indegree.items() if degree == 0)
    ordered: list[str] = []
    while queue:
        source = queue.popleft()
        ordered.append(source)
        for target in outgoing[source]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    return ordered
