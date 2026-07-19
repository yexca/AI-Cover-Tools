from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict, deque
from pathlib import Path
from threading import RLock
from typing import Any

from .model_registry import ModelRegistry
from .paths import WORKFLOWS_PATH
from .schemas import Workflow, utc_now


class WorkflowValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


class WorkflowStore:
    def __init__(self, path: Path = WORKFLOWS_PATH) -> None:
        self.path = path
        self._lock = RLock()

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=self.path.name, suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(value, stream, indent=2, ensure_ascii=False)
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            values = self._read().values()
            return sorted(
                ({"id": item["id"], "name": item.get("name", "Untitled workflow"), "updated_at": item.get("updated_at")} for item in values),
                key=lambda item: item.get("updated_at") or "",
                reverse=True,
            )

    def get(self, workflow_id: str) -> Workflow | None:
        with self._lock:
            value = self._read().get(workflow_id)
        return Workflow.model_validate(value) if value else None

    def save(self, workflow: Workflow) -> Workflow:
        workflow.updated_at = utc_now()
        with self._lock:
            values = self._read()
            values[workflow.id] = workflow.model_dump(mode="json")
            self._write(values)
        return workflow

    def delete(self, workflow_id: str) -> bool:
        with self._lock:
            values = self._read()
            existed = values.pop(workflow_id, None) is not None
            if existed:
                self._write(values)
        return existed


def validate_workflow(workflow: Workflow, registry: ModelRegistry) -> list[str]:
    errors: list[str] = []
    node_by_id = {node.id: node for node in workflow.nodes}
    if len(node_by_id) != len(workflow.nodes):
        errors.append("Node IDs must be unique")
    if not workflow.nodes:
        errors.append("Workflow has no nodes")
    incoming: dict[str, list[str]] = defaultdict(list)
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in workflow.edges:
        if edge.source not in node_by_id:
            errors.append(f"Edge {edge.id} has an unknown source node: {edge.source}")
            continue
        if edge.target not in node_by_id:
            errors.append(f"Edge {edge.id} has an unknown target node: {edge.target}")
            continue
        if edge.source == edge.target:
            errors.append(f"Node {edge.source} cannot connect to itself")
        incoming[edge.target].append(edge.source)
        outgoing[edge.source].append(edge.target)

        source_type = node_by_id[edge.source].type
        target_type = node_by_id[edge.target].type
        if source_type == "output_folder":
            errors.append(f"Output node {edge.source} cannot have outgoing edges")
        if target_type in {"input_file", "input_folder"}:
            errors.append(f"Input node {edge.target} cannot have incoming edges")

    for node in workflow.nodes:
        data = node.data
        if node.type == "input_file" and not data.get("path"):
            errors.append(f"Input file node {node.id} is missing path")
        elif node.type == "input_folder" and not data.get("path"):
            errors.append(f"Input folder node {node.id} is missing path")
        elif node.type == "separator":
            filename = data.get("model_filename") or data.get("model")
            if not filename:
                errors.append(f"Separator node {node.id} is missing model_filename")
            else:
                model = registry.find(str(filename))
                if not model:
                    errors.append(f"Separator node {node.id} uses an unknown model: {filename}")
                elif not model.get("installed"):
                    errors.append(f"Separator model is not installed: {filename}")
                output_names = set(model.get("outputs") or []) if model else set()
                for edge in workflow.edges:
                    if edge.source == node.id and edge.source_handle and output_names and edge.source_handle not in output_names:
                        errors.append(f"Separator node {node.id} has no output stem: {edge.source_handle}")
            if not incoming[node.id]:
                errors.append(f"Separator node {node.id} has no audio input")
        elif node.type == "output_folder":
            if not data.get("path"):
                errors.append(f"Output node {node.id} is missing path")
            if not incoming[node.id]:
                errors.append(f"Output node {node.id} has no audio input")

    if not any(node.type in {"input_file", "input_folder"} for node in workflow.nodes):
        errors.append("Workflow needs at least one input node")
    if not any(node.type == "output_folder" for node in workflow.nodes):
        errors.append("Workflow needs at least one output node")

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
        errors.append("Workflow contains a cycle")
    return errors


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
