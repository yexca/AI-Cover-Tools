from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .paths import BACKGROUND_IMAGE


@dataclass
class AppearanceSettings:
    background_image: Path = BACKGROUND_IMAGE
    blur_radius: int = 10
    text_color: str = "#f7f9fc"
    tint_color: str = "#04070c"
    tint_opacity: int = 104
