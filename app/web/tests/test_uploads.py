from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.web.executor import RunManager
from app.web.main import create_app
from app.web.model_registry import ModelRegistry
from app.web.uploads import AudioUploadError, AudioUploadStore
from app.web.workflows import WorkflowStore


class UploadTests(unittest.TestCase):
    def test_browser_upload_is_content_addressed_and_runs_by_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = ModelRegistry(root / "models", root / "registry.json")
            uploads = AudioUploadStore(root / "uploads")
            manager = RunManager(registry, root / "runs", uploads.directory)
            app = create_app(registry, WorkflowStore(root / "workflows.json"), manager, uploads)
            output = root / "output"

            with TestClient(app) as client:
                response = client.post(
                    "/api/uploads/audio",
                    params={"filename": "song.wav"},
                    content=b"audio-bytes",
                    headers={"Content-Type": "audio/wav"},
                )
                self.assertEqual(response.status_code, 201, response.text)
                upload = response.json()
                self.assertEqual(upload["name"], "song.wav")
                self.assertFalse(upload["reused"])
                self.assertEqual(uploads.resolve(upload["id"]).read_bytes(), b"audio-bytes")

                duplicate = client.post(
                    "/api/uploads/audio",
                    params={"filename": "renamed.wav"},
                    content=b"audio-bytes",
                )
                self.assertEqual(duplicate.json()["id"], upload["id"])
                self.assertTrue(duplicate.json()["reused"])

                workflow = {
                    "nodes": [
                        {
                            "id": "input",
                            "type": "input_file",
                            "data": {"upload_id": upload["id"], "upload_name": upload["name"]},
                        },
                        {"id": "output", "type": "output_folder", "data": {"path": str(output)}},
                    ],
                    "edges": [{"source": "input", "target": "output"}],
                }
                self.assertTrue(client.post("/api/workflows/validate", json=workflow).json()["valid"])
                run = client.post("/api/runs", json={"workflow": workflow})
                self.assertEqual(run.status_code, 202, run.text)
                deadline = time.monotonic() + 3
                state = client.get(f"/api/runs/{run.json()['id']}").json()
                while state["status"] not in {"completed", "failed", "cancelled"}:
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(0.02)
                    state = client.get(f"/api/runs/{run.json()['id']}").json()

            self.assertEqual(state["status"], "completed", state.get("error"))
            self.assertEqual((output / "song_audio.wav").read_bytes(), b"audio-bytes")

    def test_upload_rejects_unsupported_and_empty_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = ModelRegistry(root / "models", root / "registry.json")
            uploads = AudioUploadStore(root / "uploads")
            manager = RunManager(registry, root / "runs", uploads.directory)
            app = create_app(registry, WorkflowStore(root / "workflows.json"), manager, uploads)
            with TestClient(app) as client:
                unsupported = client.post("/api/uploads/audio", params={"filename": "notes.txt"}, content=b"text")
                empty = client.post("/api/uploads/audio", params={"filename": "empty.wav"}, content=b"")
            self.assertEqual(unsupported.status_code, 400)
            self.assertEqual(unsupported.json()["error"]["code"], "unsupported_audio_file")
            self.assertEqual(empty.status_code, 400)
            self.assertEqual(empty.json()["error"]["code"], "empty_audio_file")
            self.assertEqual(list(uploads.directory.glob("*")), [])

    def test_upload_reference_cannot_escape_store(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = AudioUploadStore(Path(temporary))
            with self.assertRaises(AudioUploadError) as raised:
                store.resolve("../song.wav")
            self.assertEqual(raised.exception.code, "invalid_upload_id")

    def test_upload_reference_cannot_follow_symlink_outside_store(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = AudioUploadStore(root / "uploads")
            store.directory.mkdir()
            outside = root / "outside.wav"
            outside.write_bytes(b"audio")
            upload_id = f"{'a' * 64}.wav"
            try:
                (store.directory / upload_id).symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"File symlinks are unavailable: {exc}")
            with self.assertRaises(AudioUploadError) as raised:
                store.resolve(upload_id)
            self.assertEqual(raised.exception.code, "invalid_upload_id")


if __name__ == "__main__":
    unittest.main()
