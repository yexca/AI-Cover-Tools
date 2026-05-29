from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from app.config import defaults


def load_config(config_path: Path) -> ModuleType:
    path = config_path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    spec = importlib.util.spec_from_file_location("ai_cover_user_config", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load config file: {path}")

    user_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(user_config)

    merged = ModuleType("ai_cover_runtime_config")
    _copy_public_attrs(defaults, merged)
    _copy_public_attrs(user_config, merged)
    _apply_shared_model_defaults(merged)
    return merged


def _copy_public_attrs(source: ModuleType, target: ModuleType) -> None:
    for name in dir(source):
        if name.isupper():
            setattr(target, name, getattr(source, name))


def _apply_shared_model_defaults(config: ModuleType) -> None:
    shared_defaults = {
        "batch_size": getattr(config, "MODEL_BATCH_SIZE", None),
        "overlap": getattr(config, "MODEL_OVERLAP", None),
        "segment_size": getattr(config, "MODEL_SEGMENT_SIZE", None),
        "override_model_segment_size": getattr(config, "MODEL_OVERRIDE_SEGMENT_SIZE", None),
    }
    pipeline = []
    for step in getattr(config, "MODEL_PIPELINE", []):
        merged_step = dict(step)
        for key, value in shared_defaults.items():
            if value is not None:
                merged_step.setdefault(key, value)
        pipeline.append(merged_step)
    config.MODEL_PIPELINE = pipeline
