from __future__ import annotations

import logging
from pathlib import Path
from types import ModuleType


def ensure_models(config: ModuleType) -> None:
    from audio_separator.separator import Separator

    model_dir = Path(config.MODELS_DIR)
    model_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("ai_cover.models")
    separator = Separator(info_only=True, model_file_dir=str(model_dir))

    for step in getattr(config, "MODEL_PIPELINE", []):
        model_filename = step["model_filename"]
        model_path = model_dir / model_filename
        verify_related = bool(getattr(config, "VERIFY_RELATED_MODEL_FILES", True))

        if model_path.exists() and not verify_related:
            logger.info("Model exists, skipping related-file verification: %s", model_filename)
            continue

        try:
            separator.download_model_and_data(model_filename)
        except Exception as exc:
            if not model_path.exists():
                raise RuntimeError(f"Model does not exist and download failed: {model_filename}") from exc
            raise RuntimeError(f"Model related-file check failed: {model_filename}") from exc
