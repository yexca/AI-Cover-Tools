from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.web.dialogs import (
    DialogBusyError,
    DialogError,
    _pick_path_tk,
    _pick_path_windows,
    is_loopback_client,
    pick_path,
)
from app.web.main import create_app
from app.web.model_registry import ModelRegistry
from app.web.workflows import WorkflowStore


class _Root:
    def __init__(self) -> None:
        self.destroyed = False

    def withdraw(self) -> None:
        pass

    def attributes(self, *_: object) -> None:
        pass

    def update_idletasks(self) -> None:
        pass

    def destroy(self) -> None:
        self.destroyed = True


class DialogTests(unittest.TestCase):
    def test_loopback_detection(self) -> None:
        self.assertTrue(is_loopback_client("127.0.0.1"))
        self.assertTrue(is_loopback_client("::1"))
        self.assertTrue(is_loopback_client("::ffff:127.0.0.1"))
        self.assertFalse(is_loopback_client("192.168.1.20"))

    def test_picker_is_mocked_and_root_is_destroyed_on_cancel(self) -> None:
        root = _Root()
        tk = Mock()
        tk.Tk.return_value = root
        filedialog = Mock()
        filedialog.askopenfilename.return_value = ""
        with patch("app.web.dialogs._load_tk", return_value=(tk, filedialog)):
            selected = _pick_path_tk("audio_file", None, "en")
        self.assertEqual(selected, "")
        with patch("app.web.dialogs._pick_dialog_backend", return_value=selected):
            result = pick_path("audio_file")
        self.assertEqual(result, {"path": None, "cancelled": True, "error": None})
        self.assertTrue(root.destroyed)
        self.assertIn("*.wav", filedialog.askopenfilename.call_args.kwargs["filetypes"][0][1])

    def test_picker_localizes_title_and_rejects_non_audio_selection(self) -> None:
        root = _Root()
        tk = Mock()
        tk.Tk.return_value = root
        filedialog = Mock()
        filedialog.askopenfilename.return_value = "notes.txt"
        with patch("app.web.dialogs._load_tk", return_value=(tk, filedialog)):
            selected = _pick_path_tk("audio_file", None, "ja")
        with patch("app.web.dialogs._pick_dialog_backend", return_value=selected):
            with self.assertRaises(DialogError) as raised:
                pick_path("audio_file", locale="ja")
        self.assertEqual(raised.exception.code, "unsupported_audio_file")
        self.assertEqual(filedialog.askopenfilename.call_args.kwargs["title"], "音声ファイルを選択")
        self.assertTrue(root.destroyed)

    def test_windows_picker_uses_localized_environment_without_shell_interpolation(self) -> None:
        completed = Mock(
            returncode=0,
            stdout='AUDIOFLOW_DIALOG_RESULT={"path": "C:\\\\Music\\\\song.wav"}\n',
            stderr="",
        )
        with patch("app.web.dialogs.subprocess.run", return_value=completed) as run:
            selected = _pick_path_windows("audio_file", "C:\\Music", "zh-CN")
        self.assertEqual(selected, "C:\\Music\\song.wav")
        arguments = run.call_args.args[0]
        environment = run.call_args.kwargs["env"]
        self.assertNotIn("C:\\Music", arguments)
        self.assertEqual(environment["AUDIOFLOW_INITIAL_PATH"], "C:\\Music")
        self.assertEqual(environment["AUDIOFLOW_DIALOG_TITLE"], "选择音频文件")

    def test_picker_rejects_concurrent_dialog(self) -> None:
        with patch("app.web.dialogs._DIALOG_LOCK") as lock:
            lock.acquire.return_value = False
            with self.assertRaises(DialogBusyError):
                pick_path("input_directory")
            lock.release.assert_not_called()

    def test_loopback_api_returns_mocked_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = create_app(
                ModelRegistry(root / "models", root / "registry.json"),
                WorkflowStore(root / "workflows.json"),
            )
            selected = str((root / "audio.wav").resolve())
            with patch("app.web.main.pick_path", return_value={"path": selected, "cancelled": False, "error": None}):
                with TestClient(app, client=("127.0.0.1", 50100)) as client:
                    response = client.post("/api/dialog/pick", json={"kind": "audio_file"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["path"], selected)

    def test_non_loopback_api_is_rejected_without_opening_dialog(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = create_app(
                ModelRegistry(root / "models", root / "registry.json"),
                WorkflowStore(root / "workflows.json"),
            )
            with patch("app.web.main.pick_path") as picker:
                with TestClient(app, client=("192.168.1.20", 50100)) as client:
                    response = client.post("/api/dialog/pick", json={"kind": "input_directory"})
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["error"]["code"], "loopback_required")
            picker.assert_not_called()

    def test_dialog_exception_has_stable_error_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = create_app(
                ModelRegistry(root / "models", root / "registry.json"),
                WorkflowStore(root / "workflows.json"),
            )
            with patch("app.web.main.pick_path", side_effect=RuntimeError("desktop unavailable")):
                with TestClient(app, client=("127.0.0.1", 50100)) as client:
                    response = client.post("/api/dialog/pick", json={"kind": "output_directory"})
            self.assertEqual(response.status_code, 500)
            self.assertEqual(
                response.json(),
                {
                    "path": None,
                    "cancelled": False,
                    "error": {"code": "dialog_failed", "message": "desktop unavailable"},
                },
            )

    def test_dialog_busy_has_stable_conflict_response(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = create_app(
                ModelRegistry(root / "models", root / "registry.json"),
                WorkflowStore(root / "workflows.json"),
            )
            with patch("app.web.main.pick_path", side_effect=DialogBusyError()):
                with TestClient(app, client=("127.0.0.1", 50100)) as client:
                    response = client.post("/api/dialog/pick", json={"kind": "output_directory", "locale": "zh-CN"})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["error"]["code"], "dialog_busy")


if __name__ == "__main__":
    unittest.main()
