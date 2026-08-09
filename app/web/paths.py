from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT_DIR / "models"
USER_DATA_DIR = ROOT_DIR / "user_data"
REGISTRY_PATH = USER_DATA_DIR / "model_registry.json"
WORKFLOWS_DIR = USER_DATA_DIR / "workflows"
LEGACY_WORKFLOWS_PATH = USER_DATA_DIR / "web_workflows.json"
RUNS_DIR = USER_DATA_DIR / "web_runs"
UPLOADS_DIR = USER_DATA_DIR / "web_uploads"
SEPARATOR_SOURCE_DIR = ROOT_DIR / "sample" / "python-audio-separator"
SEPARATOR_DATA_DIR = SEPARATOR_SOURCE_DIR / "audio_separator"
STATIC_DIR = Path(__file__).resolve().parent / "static"
