from __future__ import annotations

import tempfile
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


if __name__ == "__main__":
    unittest.main()
