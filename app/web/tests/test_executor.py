from __future__ import annotations

import asyncio
import json
import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from app.web.executor import AudioArtifact, RunManager, RunState
from app.web.model_registry import ModelRegistry
from app.web.schemas import Workflow


class ExecutorTests(unittest.TestCase):
    def test_unconnected_separator_branch_is_not_executed(self) -> None:
        class PruningRunManager(RunManager):
            def _separate(self, *args, **kwargs):
                raise AssertionError("unconnected separator should not execute")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "song.wav"
            source.write_bytes(b"audio")
            output = root / "output"
            manager = PruningRunManager(ModelRegistry(root / "models", root / "registry.json"), root / "runs")
            workflow = Workflow.model_validate(
                {
                    "nodes": [
                        {"id": "input", "type": "input_file", "data": {"path": str(source)}},
                        {"id": "unused", "type": "separator", "data": {"model_filename": "unused.ckpt"}},
                        {"id": "output", "type": "output_folder", "data": {"path": str(output)}},
                    ],
                    "edges": [
                        {"source": "input", "target": "unused"},
                        {"source": "input", "target": "output"},
                    ],
                }
            )
            try:
                run_id = manager.submit(workflow)["id"]
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    state = manager.get(run_id)
                    if state and state["status"] in {"completed", "failed", "cancelled"}:
                        break
                    time.sleep(0.02)
            finally:
                manager.shutdown()

            self.assertEqual(state["status"], "completed", state.get("error"))
            self.assertTrue((output / "song_audio.wav").is_file())

    def test_smart_classification_uses_model_stem_and_relative_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.wav"
            source.write_bytes(b"audio")
            manager = RunManager(ModelRegistry(root / "models", root / "registry.json"), root / "runs")
            try:
                written = manager._write_outputs(
                    RunState(id="run", workflow_id="workflow", workflow_name="Workflow"),
                    "output",
                    {"path": str(root / "output"), "mode": "smart_classification", "format": "same"},
                    [
                        AudioArtifact(
                            path=source,
                            basename="song",
                            relative_dir=Path("album") / "disc-1",
                            stem="Lead Vocals",
                            model="Model Name",
                            node="split",
                        )
                    ],
                )
            finally:
                manager.shutdown()

            expected = root / "output" / "Model_Name_Lead_Vocals" / "album" / "disc-1" / "song.wav"
            self.assertEqual(written, [expected])
            self.assertEqual(expected.read_bytes(), b"audio")
    def test_file_to_output_workflow_runs_without_separator(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "song.wav"
            source.write_bytes(b"test-audio-placeholder")
            output = root / "output"
            registry = ModelRegistry(root / "models", root / "registry.json")
            manager = RunManager(registry, root / "runs")
            workflow = Workflow.model_validate(
                {
                    "id": "copy-test",
                    "nodes": [
                        {"id": "input", "type": "input_file", "data": {"path": str(source)}},
                        {
                            "id": "output",
                            "type": "output_folder",
                            "data": {"path": str(output), "naming_template": "{basename}_{stem}.{ext}", "format": "same"},
                        },
                    ],
                    "edges": [{"source": "input", "source_handle": "audio", "target": "output"}],
                }
            )
            run_id = manager.submit(workflow)["id"]
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                state = manager.get(run_id)
                if state and state["status"] in {"completed", "failed", "cancelled"}:
                    break
                time.sleep(0.02)
            manager.shutdown()

            self.assertEqual(state["status"], "completed")
            self.assertEqual((output / "song_audio.wav").read_bytes(), source.read_bytes())

    def test_slicer_and_peak_normalize_chain_routes_generated_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "song.wav"
            with wave.open(str(source), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(16000)
                stream.writeframes(b"\x00\x00" * 1600)
            output = root / "output"
            manager = RunManager(ModelRegistry(root / "models", root / "registry.json"), root / "runs")
            workflow = Workflow.model_validate(
                {
                    "id": "prepare-test",
                    "nodes": [
                        {"id": "input", "type": "input_file", "data": {"path": str(source)}},
                        {"id": "slice", "type": "slicer", "data": {"output_format": "wav"}},
                        {"id": "normalize", "type": "peak_normalize", "data": {"target_peak_db": -3}},
                        {
                            "id": "output",
                            "type": "output_folder",
                            "data": {"path": str(output), "naming_template": "{basename}_{stem}.{ext}", "format": "same"},
                        },
                    ],
                    "edges": [
                        {"source": "input", "target": "slice"},
                        {"source": "slice", "target": "normalize"},
                        {"source": "normalize", "target": "output"},
                    ],
                }
            )

            def fake_normalize(source_path: Path, destination_path: Path, _target: float) -> Path:
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                destination_path.write_bytes(source_path.read_bytes())
                return destination_path

            try:
                with patch("app.tools.normalize_audio_file", side_effect=fake_normalize):
                    run_id = manager.submit(workflow)["id"]
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        state = manager.get(run_id)
                        if state and state["status"] in {"completed", "failed", "cancelled"}:
                            break
                        time.sleep(0.02)
            finally:
                manager.shutdown()

            self.assertEqual(state["status"], "completed", state.get("error"))
            self.assertTrue((output / "song_000_audio.wav").is_file())
            self.assertEqual(state["outputs"], [str(output / "song_000_audio.wav")])

    def test_run_list_reports_queue_position_and_truthful_cancellation(self) -> None:
        class BlockingRunManager(RunManager):
            def __init__(self, registry: ModelRegistry, runs_dir: Path) -> None:
                super().__init__(registry, runs_dir)
                self.started = threading.Event()
                self.release = threading.Event()

            def _run_workflow(self, run, workflow):
                self.started.set()
                self.release.wait(timeout=3)
                self._check_cancel(run)
                return []

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manager = BlockingRunManager(ModelRegistry(root / "models", root / "registry.json"), root / "runs")
            try:
                first = manager.submit(Workflow(id="first", name="First workflow"))
                self.assertTrue(manager.started.wait(timeout=1))
                second = manager.submit(Workflow(id="second", name="Second workflow"))

                by_id = {item["id"]: item for item in manager.list()}
                self.assertEqual(by_id[first["id"]]["status"], "running")
                self.assertEqual(by_id[second["id"]]["status"], "queued")
                self.assertEqual(by_id[second["id"]]["queue_position"], 1)
                self.assertEqual(by_id[second["id"]]["workflow_name"], "Second workflow")

                cancelling = manager.cancel(first["id"])
                self.assertEqual(cancelling["status"], "cancelling")
                self.assertEqual(manager.get(first["id"])["status"], "cancelling")
            finally:
                manager.release.set()
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    if all(
                        manager.get(run_id)["status"] in {"completed", "failed", "cancelled"}
                        for run_id in (first["id"], second["id"])
                    ):
                        break
                    time.sleep(0.02)
                manager.shutdown()

    def test_run_state_and_workflow_snapshot_survive_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = root / "runs" / "stale-run"
            run_dir.mkdir(parents=True)
            (run_dir / "workflow.json").write_text(
                json.dumps({"id": "workflow-1", "name": "Persisted workflow", "nodes": [], "edges": []}),
                encoding="utf-8",
            )
            (run_dir / "run.json").write_text(
                json.dumps(
                    {
                        "id": "stale-run",
                        "workflow_id": "workflow-1",
                        "workflow_name": "Persisted workflow",
                        "status": "running",
                        "progress": 0.4,
                        "message": "Running",
                        "created_at": "2026-07-23T00:00:00+00:00",
                        "events": [
                            {
                                "sequence": 7,
                                "type": "started",
                                "run_id": "stale-run",
                                "timestamp": "2026-07-23T00:00:01+00:00",
                                "message": "Workflow started",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            manager = RunManager(ModelRegistry(root / "models", root / "registry.json"), root / "runs")
            try:
                restored = manager.get("stale-run")
                self.assertEqual(restored["status"], "failed")
                self.assertEqual(restored["workflow"]["id"], "workflow-1")
                self.assertIn("stopped before", restored["error"])
                snapshot = manager.snapshot()
                self.assertEqual(snapshot["active"], [])
                self.assertEqual(snapshot["history"][0]["id"], "stale-run")

                async def read_event() -> str:
                    events = manager.global_events(after_sequence=7)
                    try:
                        return await anext(events)
                    finally:
                        await events.aclose()

                event = asyncio.run(read_event())
                self.assertIn('"type": "failed"', event)
                self.assertIn("id: 8", event)
            finally:
                manager.shutdown()


if __name__ == "__main__":
    unittest.main()
