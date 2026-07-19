from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.web.model_registry import ModelRegistry


class ModelRegistryTests(unittest.TestCase):
    def test_demucs_yaml_entrypoint_is_reported_as_installed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            models = root / "models"
            models.mkdir()
            (models / "download_checks.json").write_text(
                json.dumps(
                    {
                        "demucs_download_list": {
                            "Demucs v4: test": {
                                "weights.th": "https://example.invalid/weights.th",
                                "htdemucs_test.yaml": "https://example.invalid/htdemucs_test.yaml",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            (models / "htdemucs_test.yaml").write_text("models: []\n", encoding="utf-8")

            data = ModelRegistry(models_dir=models, cache_path=root / "registry.json").refresh("local")

            model = next(item for item in data["models"] if item["filename"] == "htdemucs_test.yaml")
            self.assertTrue(model["installed"])
            self.assertEqual(model["architecture"], "Demucs")

    def test_local_yaml_supplies_stems_without_loading_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "my_denoise_roformer.ckpt").write_bytes(b"not-a-real-model")
            (root / "my_denoise_roformer.yaml").write_text(
                "training:\n  instruments: [dry, noise]\n  target_instrument: dry\n",
                encoding="utf-8",
            )
            registry = ModelRegistry(root, root / "registry.json")
            result = registry.refresh("local")
            model = next(item for item in result["models"] if item["filename"] == "my_denoise_roformer.ckpt")

            self.assertTrue(model["installed"])
            self.assertEqual(model["architecture"], "RoFormer")
            self.assertEqual(model["function"], "denoise")
            self.assertEqual(model["outputs"], ["dry", "noise"])
            self.assertEqual(model["target_stem"], "dry")
            self.assertEqual(model["metadata_source"], "yaml")

    def test_empty_snapshot_does_not_scan_synchronously(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "model.ckpt").write_bytes(b"model")
            registry = ModelRegistry(root, root / "missing-registry.json")
            result = registry.snapshot()
            self.assertTrue(result["scanning"])
            self.assertEqual(result["models"], [])


if __name__ == "__main__":
    unittest.main()
