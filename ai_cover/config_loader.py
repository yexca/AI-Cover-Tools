from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def load_config(config_path: Path) -> ModuleType:
    path = config_path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    spec = importlib.util.spec_from_file_location("ai_cover_user_config", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load config file: {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
