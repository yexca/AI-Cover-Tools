from __future__ import annotations

import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.web.executor import RunManager
from app.web.main import create_app
from app.web.model_registry import ModelRegistry
from app.web.schemas import Workflow
from app.web.workflows import WorkflowStore, validate_workflow


class FixtureRegistry:
    def __init__(self) -> None:
        self.refresh_calls: list[tuple[str, bool]] = []
        self.model = {
            "id": "fixture.ckpt",
            "filename": "fixture.ckpt",
            "display_name": "Fixture separator",
            "architecture": "RoFormer",
            "backend": "MDXC",
            "function": "vocal_separation",
            "outputs": ["vocals", "instrumental"],
            "installed": True,
            "needs_confirmation": False,
        }

    def snapshot(self):
        return {
            "version": 1,
            "models": [self.model.copy()],
            "summary": {"total": 1, "installed": 1, "needs_confirmation": 0},
        }

    def refresh(self, scope="local", force=False):
        self.refresh_calls.append((scope, force))
        return self.snapshot()

    def find(self, filename):
        return self.model.copy() if str(filename).lower() == "fixture.ckpt" else None


def workflow_payload(input_path: Path, vocals_dir: Path, instrumental_dir: Path) -> dict:
    return {
        "id": "fixture-workflow",
        "name": "branching separation",
        "version": 1,
        "nodes": [
            {"id": "input", "type": "input_file", "data": {"path": str(input_path)}},
            {
                "id": "separate",
                "type": "separator",
                "data": {
                    "model_filename": "fixture.ckpt",
                    "outputs": ["vocals", "instrumental"],
                    "options": {"output_format": "WAV"},
                },
            },
            {
                "id": "vocals-output",
                "type": "output_folder",
                "data": {"path": str(vocals_dir), "naming_template": "{basename}_{stem}.{ext}"},
            },
            {
                "id": "instrumental-output",
                "type": "output_folder",
                "data": {"path": str(instrumental_dir), "naming_template": "{basename}_{stem}.{ext}"},
            },
        ],
        "edges": [
            {"source": "input", "source_handle": "audio", "target": "separate", "target_handle": "audio"},
            {
                "source": "separate",
                "source_handle": "vocals",
                "target": "vocals-output",
                "target_handle": "audio",
            },
            {
                "source": "separate",
                "source_handle": "instrumental",
                "target": "instrumental-output",
                "target_handle": "audio",
            },
        ],
    }


class ModelRegistryTests(unittest.TestCase):
    def test_local_yaml_drives_architecture_function_and_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            models = root / "models"
            models.mkdir()
            (models / "mel_band_roformer_fixture.ckpt").write_bytes(b"not-a-real-model")
            (models / "mel_band_roformer_fixture.yaml").write_text(
                "training:\n"
                "  instruments: !!python/tuple [vocals, instrumental]\n"
                "  target_instrument: vocals\n",
                encoding="utf-8",
            )

            class OfflineRegistry(ModelRegistry):
                def _catalog_sources(self):
                    return []

                def _score_metadata(self, filename):
                    return {"outputs": [], "target_stem": None}

            registry = OfflineRegistry(models, root / "registry.json")
            snapshot = registry.refresh("local")

            self.assertEqual(snapshot["summary"]["installed"], 1)
            model = snapshot["models"][0]
            self.assertEqual(model["architecture"], "RoFormer")
            self.assertEqual(model["backend"], "MDXC")
            self.assertEqual(model["function"], "vocal_separation")
            self.assertEqual(model["outputs"], ["vocals", "instrumental"])
            self.assertEqual(model["target_stem"], "vocals")
            self.assertEqual(model["metadata_source"], "yaml")
            self.assertEqual(model["confidence"], "high")
            self.assertFalse(model["needs_confirmation"])
            self.assertTrue((root / "registry.json").is_file())

    def test_local_refresh_never_calls_online_sync(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            class OfflineRegistry(ModelRegistry):
                def _catalog_sources(self):
                    return []

            registry = OfflineRegistry(root / "models", root / "registry.json")
            with patch.object(registry, "_sync_catalog", side_effect=AssertionError("network path reached")):
                registry.refresh("local")


class WorkflowContractTests(unittest.TestCase):
    def test_editor_payload_validates_and_legacy_config_is_flattened(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "song.wav").write_bytes(b"audio")
            payload = workflow_payload(root / "song.wav", root / "vocals", root / "instrumental")
            payload["nodes"][0] = {
                "id": "input",
                "type": "file_input",
                "data": {"config": {"path": str(root / "song.wav")}},
            }
            payload["nodes"][2] = {
                "id": "vocals-output",
                "type": "output",
                "data": {"config": {"path": str(root / "vocals"), "naming": "{basename}_{stem}.{ext}"}},
            }
            workflow = Workflow.model_validate(payload)

            self.assertEqual(workflow.nodes[0].type, "input_file")
            self.assertEqual(workflow.nodes[0].data["path"], str(root / "song.wav"))
            self.assertEqual(workflow.nodes[2].type, "output_folder")
            self.assertEqual(workflow.nodes[2].data["naming_template"], "{basename}_{stem}.{ext}")
            self.assertEqual(validate_workflow(workflow, FixtureRegistry()), [])

    def test_validation_rejects_unknown_stem_and_cycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = workflow_payload(root / "song.wav", root / "vocals", root / "instrumental")
            payload["edges"][1]["source_handle"] = "imaginary"
            payload["edges"].append(
                {"source": "vocals-output", "target": "separate", "source_handle": "audio", "target_handle": "audio"}
            )
            errors = validate_workflow(Workflow.model_validate(payload), FixtureRegistry())

            self.assertTrue(any("no output stem: imaginary" in error for error in errors))
            self.assertTrue(any("cannot have outgoing edges" in error for error in errors))
            self.assertIn("Workflow contains a cycle", errors)


class DummyRunManager:
    def __init__(self):
        self.shutdown_called = False

    def shutdown(self):
        self.shutdown_called = True

    def submit(self, workflow):
        return {"id": "dummy-run", "workflow_id": workflow.id, "status": "queued"}

    def get(self, run_id):
        return None

    def cancel(self, run_id):
        return None


class ApiAndStaticTests(unittest.TestCase):
    def test_health_models_filters_static_assets_and_workflow_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "song.wav").write_bytes(b"audio")
            registry = FixtureRegistry()
            manager = DummyRunManager()
            app = create_app(registry, WorkflowStore(root / "workflows.json"), manager)
            with TestClient(app) as client:
                health = client.get("/api/health")
                self.assertEqual(health.status_code, 200)
                self.assertEqual(health.json()["status"], "ok")

                models = client.get("/api/models", params={"installed": "true", "architecture": "roformer"})
                self.assertEqual(models.status_code, 200)
                self.assertEqual(models.json()["filtered_total"], 1)
                self.assertEqual(models.json()["models"][0]["outputs"], ["vocals", "instrumental"])

                hidden = client.get("/api/models", params={"function": "denoise"})
                self.assertEqual(hidden.json()["filtered_total"], 0)

                index = client.get("/")
                self.assertEqual(index.status_code, 200)
                self.assertIn('href="/styles.css"', index.text)
                self.assertIn('src="/app.js"', index.text)
                self.assertEqual(client.get("/styles.css").status_code, 200)
                self.assertEqual(client.get("/app.js").status_code, 200)
                self.assertEqual(client.get("/static/styles.css").status_code, 200)
                javascript = client.get("/static/app.js")
                self.assertEqual(javascript.status_code, 200)
                self.assertIn("source_handle", javascript.text)
                self.assertIn("model_filename", javascript.text)
                self.assertIn("naming_template", javascript.text)
                self.assertIn("multistem_separation", javascript.text)
                self.assertIn("normalization_threshold", javascript.text)
                self.assertEqual(client.get("/api/not-a-route").status_code, 404)

                payload = workflow_payload(root / "song.wav", root / "vocals", root / "instrumental")
                created = client.post("/api/workflows", json=payload)
                self.assertEqual(created.status_code, 201)
                loaded = client.get("/api/workflows/fixture-workflow")
                self.assertEqual(loaded.status_code, 200)
                self.assertEqual(loaded.json()["edges"][1]["source_handle"], "vocals")

                validation = client.post("/api/workflows/validate", json=payload)
                self.assertEqual(validation.status_code, 200)
                self.assertTrue(validation.json()["valid"])

            self.assertTrue(manager.shutdown_called)
            self.assertIn(("local", False), registry.refresh_calls)


class ExecutorBranchingTests(unittest.TestCase):
    def test_mock_separator_routes_two_stems_to_independent_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input" / "song.wav"
            source.parent.mkdir()
            source.write_bytes(b"source-audio")
            vocals_dir = root / "vocals"
            instrumental_dir = root / "instrumental"
            payload = workflow_payload(source, vocals_dir, instrumental_dir)
            payload["nodes"][3]["data"]["format"] = "flac"
            workflow = Workflow.model_validate(payload)

            fake_package = types.ModuleType("audio_separator")
            fake_separator_module = types.ModuleType("audio_separator.separator")

            class FakeSeparator:
                instances = []

                def __init__(self, **kwargs):
                    self.output_dir = Path(kwargs["output_dir"])
                    self.loaded = None
                    self.__class__.instances.append(self)

                def load_model(self, model_filename):
                    self.loaded = model_filename

                def separate(self, audio_path, custom_output_names=None):
                    paths = []
                    for stem in ("vocals", "instrumental"):
                        output = self.output_dir / f"{custom_output_names[stem]}.wav"
                        output.write_bytes(f"{stem}:{Path(audio_path).name}".encode())
                        paths.append(str(output))
                    return paths

            fake_separator_module.Separator = FakeSeparator

            def fake_ffmpeg(command, **kwargs):
                source_path = Path(command[command.index("-i") + 1])
                Path(command[-1]).write_bytes(source_path.read_bytes())
                return types.SimpleNamespace(returncode=0, stderr="")

            manager = RunManager(FixtureRegistry())
            try:
                with patch.dict(
                    sys.modules,
                    {"audio_separator": fake_package, "audio_separator.separator": fake_separator_module},
                ), patch("app.web.executor.RUNS_DIR", root / "runs"), patch(
                    "app.web.executor.MODELS_DIR", root / "models"
                ), patch("app.web.executor.shutil.which", return_value="ffmpeg"), patch(
                    "app.web.executor.subprocess.run", side_effect=fake_ffmpeg
                ):
                    submitted = manager.submit(workflow)
                    deadline = time.monotonic() + 5
                    result = manager.get(submitted["id"])
                    while result["status"] not in {"completed", "failed", "cancelled"}:
                        self.assertLess(time.monotonic(), deadline, "mock workflow did not finish")
                        time.sleep(0.01)
                        result = manager.get(submitted["id"])
            finally:
                manager.shutdown()

            self.assertEqual(result["status"], "completed", result.get("error"))
            self.assertEqual(FakeSeparator.instances[0].loaded, "fixture.ckpt")
            self.assertEqual(
                {Path(path).name for path in result["outputs"]},
                {"song_vocals.wav", "song_instrumental.flac"},
            )
            self.assertEqual((vocals_dir / "song_vocals.wav").read_bytes(), b"vocals:song.wav")
            self.assertEqual(
                (instrumental_dir / "song_instrumental.flac").read_bytes(), b"instrumental:song.wav"
            )


if __name__ == "__main__":
    unittest.main()
