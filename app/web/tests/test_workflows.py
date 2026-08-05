from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.web.executor import RunManager
from app.web.main import create_app
from app.web.model_registry import ModelRegistry
from app.web.schemas import RunRequest, Workflow
from app.web.workflows import WorkflowStore, topological_order, validate_workflow, validate_workflow_detailed


class _Registry:
    def find(self, filename: str):
        if filename == "test.ckpt":
            return {"installed": True, "outputs": ["vocals", "other"]}
        return None


class WorkflowTests(unittest.TestCase):
    def test_workflow_api_manages_multiple_saved_workflows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = create_app(
                ModelRegistry(root / "models", root / "registry.json"),
                WorkflowStore(root / "workflows.json"),
                RunManager(ModelRegistry(root / "models", root / "run-registry.json"), root / "runs"),
            )
            with TestClient(app, client=("127.0.0.1", 50100)) as client:
                first = client.post("/api/workflows", json={"id": "first", "name": "First"})
                second = client.post("/api/workflows", json={"id": "second", "name": "Second"})
                self.assertEqual(first.status_code, 201)
                self.assertEqual(second.status_code, 201)
                self.assertEqual(first.json()["revision"], 1)
                self.assertEqual({item["id"] for item in client.get("/api/workflows").json()["workflows"]}, {"first", "second"})

                updated = client.put(
                    "/api/workflows/first",
                    json={"id": "ignored", "name": "Renamed", "revision": first.json()["revision"]},
                )
                self.assertEqual(updated.json()["id"], "first")
                self.assertEqual(updated.json()["revision"], 2)
                self.assertEqual(client.get("/api/workflows/first").json()["name"], "Renamed")
                self.assertEqual(client.delete("/api/workflows/second").status_code, 200)
                self.assertEqual([item["id"] for item in client.get("/api/workflows").json()["workflows"]], ["first"])

                self.assertEqual(client.post("/api/workflows", json={"id": "first"}).status_code, 409)
                self.assertEqual(
                    client.put("/api/workflows/first", json={"name": "Stale", "revision": 1}).status_code,
                    409,
                )
                self.assertEqual(
                    client.put("/api/workflows/missing", json={"name": "Missing", "revision": 1}).status_code,
                    404,
                )

            workflow_files = list((root / "workflows").glob("*.json"))
            self.assertEqual(len(workflow_files), 1)
            self.assertEqual(json.loads(workflow_files[0].read_text(encoding="utf-8"))["id"], "first")

    def test_legacy_workflow_blob_is_migrated_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            legacy = Path(temporary) / "workflows.json"
            legacy.write_text(
                json.dumps(
                    {
                        "first": {"id": "first", "name": "First"},
                        "second": {"id": "second", "name": "Second"},
                    }
                ),
                encoding="utf-8",
            )

            store = WorkflowStore(legacy)
            self.assertEqual({item["id"] for item in store.list()}, {"first", "second"})
            self.assertTrue(legacy.exists())
            self.assertTrue((legacy.with_suffix("") / ".legacy-migrated").exists())

            self.assertTrue(store.delete("second"))
            reloaded = WorkflowStore(legacy)
            self.assertEqual([item["id"] for item in reloaded.list()], ["first"])

    def test_editor_payload_is_normalized_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "song.wav"
            source.write_bytes(b"audio")
            raw = {
                "id": "workflow-1",
                "name": "Vocal split",
                "nodes": [
                    {
                        "id": "input",
                        "type": "file_input",
                        "data": {"width": 310, "height": 180, "config": {"path": str(source)}},
                    },
                    {"id": "split", "type": "separator", "data": {"model_filename": "test.ckpt", "config": {"output_format": "wav"}}},
                    {"id": "output", "type": "output", "data": {"config": {"path": str(root / "outputs"), "naming": "{basename}_{stem}.{ext}"}}},
                ],
                "edges": [
                    {"source": "input", "source_handle": "audio", "target": "split", "target_handle": "audio"},
                    {"source": "split", "source_handle": "vocals", "target": "output", "target_handle": "audio"},
                ],
            }
            workflow = Workflow.model_validate(raw)
            self.assertEqual([node.type for node in workflow.nodes], ["input_file", "separator", "output_folder"])
            self.assertEqual(workflow.nodes[0].data["path"], str(source))
            self.assertEqual(workflow.nodes[0].data["width"], 310)
            self.assertEqual(workflow.nodes[0].data["height"], 180)
            self.assertEqual(workflow.nodes[2].data["naming_template"], "{basename}_{stem}.{ext}")
            self.assertEqual(validate_workflow(workflow, _Registry()), [])
            self.assertEqual(topological_order(workflow), ["input", "split", "output"])
            self.assertEqual(RunRequest.model_validate(raw).workflow.id, "workflow-1")

    def test_unknown_separator_stem_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "song.wav"
            source.write_bytes(b"audio")
            workflow = Workflow.model_validate(
                {
                    "nodes": [
                        {"id": "input", "type": "input_file", "data": {"path": str(source)}},
                        {"id": "split", "type": "separator", "data": {"model_filename": "test.ckpt"}},
                        {"id": "output", "type": "output_folder", "data": {"path": str(root / "outputs")}},
                    ],
                    "edges": [
                        {"source": "input", "target": "split"},
                        {"source": "split", "source_handle": "drums", "target": "output"},
                    ],
                }
            )
            errors = validate_workflow(workflow, _Registry())
            self.assertTrue(any("no output stem: drums" in error for error in errors))
            details = validate_workflow_detailed(workflow, _Registry())
            stem_edge_id = workflow.edges[1].id
            self.assertFalse(details["valid"])
            self.assertIn(stem_edge_id, details["edge_errors"])
            self.assertEqual(details["node_errors"], {})
            self.assertEqual(details["errors"], errors)

    def test_slicer_and_peak_normalize_nodes_validate_as_audio_transforms(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "song.wav"
            source.write_bytes(b"audio")
            workflow = Workflow.model_validate(
                {
                    "nodes": [
                        {"id": "input", "type": "input_file", "data": {"path": str(source)}},
                        {
                            "id": "slice",
                            "type": "slicer",
                            "data": {
                                "config": {
                                    "threshold": -45,
                                    "min_length": 5000,
                                    "min_interval": 300,
                                    "hop_size": 10,
                                    "max_sil_kept": 1000,
                                    "output_format": "wav",
                                }
                            },
                        },
                        {"id": "normalize", "type": "peak_normalize", "data": {"target_peak_db": -3}},
                        {"id": "output", "type": "output_folder", "data": {"path": str(root / "outputs")}},
                    ],
                    "edges": [
                        {"source": "input", "target": "slice"},
                        {"source": "slice", "target": "normalize"},
                        {"source": "normalize", "target": "output"},
                    ],
                }
            )
            self.assertEqual(workflow.nodes[1].data["threshold"], -45)
            self.assertEqual(validate_workflow(workflow, _Registry()), [])

    def test_invalid_audio_transform_settings_are_keyed_by_node_id(self) -> None:
        workflow = Workflow.model_validate(
            {
                "nodes": [
                    {"id": "input", "type": "input_folder", "data": {"path": "."}},
                    {
                        "id": "slice",
                        "type": "slicer",
                        "data": {"min_length": 10, "min_interval": 20, "hop_size": 30},
                    },
                    {"id": "normalize", "type": "peak_normalize", "data": {"target_peak_db": 1}},
                    {"id": "output", "type": "output_folder", "data": {"path": "outputs"}},
                ],
                "edges": [
                    {"source": "input", "target": "slice"},
                    {"source": "slice", "target": "normalize"},
                    {"source": "normalize", "target": "output"},
                ],
            }
        )
        details = validate_workflow_detailed(workflow, _Registry())
        self.assertFalse(details["valid"])
        self.assertIn("slice", details["node_errors"])
        self.assertIn("normalize", details["node_errors"])

    def test_missing_node_values_are_keyed_by_node_id(self) -> None:
        workflow = Workflow.model_validate(
            {
                "nodes": [
                    {"id": "input", "type": "input_file", "data": {}},
                    {"id": "output", "type": "output_folder", "data": {}},
                ],
                "edges": [{"id": "edge-1", "source": "input", "target": "output"}],
            }
        )
        details = validate_workflow_detailed(workflow, _Registry())
        self.assertIn("input", details["node_errors"])
        self.assertIn("output", details["node_errors"])
        self.assertEqual(details["edge_errors"], {})

    def test_invalid_ports_and_missing_paths_are_keyed(self) -> None:
        workflow = Workflow.model_validate(
            {
                "nodes": [
                    {"id": "input", "type": "input_file", "data": {"path": "missing.wav"}},
                    {"id": "output", "type": "output_folder", "data": {"path": "outputs"}},
                ],
                "edges": [
                    {
                        "id": "bad-port",
                        "source": "input",
                        "source_handle": "not_audio",
                        "target": "output",
                        "target_handle": "not_audio",
                    }
                ],
            }
        )
        details = validate_workflow_detailed(workflow, _Registry())
        self.assertIn("input", details["node_errors"])
        self.assertEqual(len(details["edge_errors"]["bad-port"]), 2)

    def test_validation_and_run_apis_return_structured_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = create_app(
                ModelRegistry(root / "models", root / "registry.json"),
                WorkflowStore(root / "workflows.json"),
                RunManager(ModelRegistry(root / "models", root / "run-registry.json"), root / "runs"),
            )
            workflow = {
                "nodes": [
                    {"id": "input", "type": "input_file", "data": {}},
                    {"id": "output", "type": "output_folder", "data": {}},
                ],
                "edges": [{"id": "edge-1", "source": "input", "target": "output"}],
            }
            with TestClient(app, client=("127.0.0.1", 50100)) as client:
                validation = client.post("/api/workflows/validate", json=workflow)
                run = client.post("/api/runs", json={"workflow": workflow})
            self.assertEqual(validation.status_code, 200)
            self.assertFalse(validation.json()["valid"])
            self.assertEqual(set(validation.json()["node_errors"]), {"input", "output"})
            self.assertEqual(run.status_code, 422)
            self.assertEqual(set(run.json()["detail"]["node_errors"]), {"input", "output"})


if __name__ == "__main__":
    unittest.main()
