from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..paths import PROJECT_ROOT


MODEL_CATEGORIES = ("instrumental", "harmony", "reverb", "noise")

DATA_DIR = PROJECT_ROOT / "user_data"
MODEL_LIBRARY_PATH = DATA_DIR / "separate_models.json"
PRESETS_PATH = DATA_DIR / "separate_presets.json"


DEFAULT_MODULES: dict[str, dict[str, Any]] = {
    "instrumental": {
        "label": "vocals",
        "model_filename": "mel_band_roformer_kim_ft3_unwa.ckpt",
        "keep_stem": "vocals",
        "stem_aliases": ["Vocals", "vocal"],
        "pitch_shift": 0,
    },
    "harmony": {
        "label": "deharmony",
        "model_filename": "",
        "keep_stem": "vocals",
        "stem_aliases": ["Vocals", "vocal"],
        "pitch_shift": 0,
    },
    "reverb": {
        "label": "dereverb",
        "model_filename": "",
        "keep_stem": "dry",
        "stem_aliases": ["Dry", "No Reverb"],
        "pitch_shift": 0,
    },
    "noise": {
        "label": "denoise",
        "model_filename": "",
        "keep_stem": "clean",
        "stem_aliases": ["Clean", "Denoised"],
        "pitch_shift": 0,
    },
}


class SeparateStore:
    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def load_model_library(self) -> dict[str, dict[str, dict[str, Any]]]:
        data = self._read_json(MODEL_LIBRARY_PATH, {})
        library = {category: {} for category in MODEL_CATEGORIES}
        for category, models in data.items():
            if category in library and isinstance(models, dict):
                library[category].update(models)
        return library

    def save_successful_models(self, modules: list[dict[str, Any]]) -> None:
        library = self.load_model_library()
        for module in modules:
            category = str(module.get("category", ""))
            model = dict(module.get("model", {}))
            model_filename = str(model.get("model_filename", "")).strip()
            if category in library and model_filename:
                library[category][model_filename] = model
        self._write_json(MODEL_LIBRARY_PATH, library)

    def default_module(self, category: str) -> dict[str, Any]:
        model = deepcopy(DEFAULT_MODULES.get(category, DEFAULT_MODULES["instrumental"]))
        library = self.load_model_library().get(category, {})
        if library:
            model.update(deepcopy(next(iter(library.values()))))
        return {"category": category, "model": model}

    def load_presets(self) -> dict[str, dict[str, Any]]:
        data = self._read_json(PRESETS_PATH, {})
        return data if isinstance(data, dict) else {}

    def save_preset(self, name: str, payload: dict[str, Any]) -> None:
        presets = self.load_presets()
        presets[name] = payload
        self._write_json(PRESETS_PATH, presets)

    def delete_preset(self, name: str) -> None:
        presets = self.load_presets()
        presets.pop(name, None)
        self._write_json(PRESETS_PATH, presets)

    def _read_json(self, path: Path, fallback: Any) -> Any:
        if not path.exists():
            return deepcopy(fallback)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return deepcopy(fallback)

    def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
