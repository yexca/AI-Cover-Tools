from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app.web.executor import RunManager
from app.web.model_registry import ModelRegistry
from app.web.schemas import Workflow


class ExecutorTests(unittest.TestCase):
    def test_file_to_output_workflow_runs_without_separator(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "song.wav"
            source.write_bytes(b"test-audio-placeholder")
            output = root / "output"
            registry = ModelRegistry(root / "models", root / "registry.json")
            manager = RunManager(registry)
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
            with patch("app.web.executor.RUNS_DIR", root / "runs"):
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

    def test_run_list_reports_queue_position_and_truthful_cancellation(self) -> None:
        class BlockingRunManager(RunManager):
            def __init__(self, registry: ModelRegistry) -> None:
                super().__init__(registry)
                self.started = threading.Event()
                self.release = threading.Event()

            def _run_workflow(self, run, workflow):
                self.started.set()
                self.release.wait(timeout=3)
                self._check_cancel(run)
                return []

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manager = BlockingRunManager(ModelRegistry(root / "models", root / "registry.json"))
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
                manager.shutdown()


if __name__ == "__main__":
    unittest.main()
