from __future__ import annotations

import locale
from dataclasses import dataclass

from ..bootstrap import configure_windows_dll_paths

configure_windows_dll_paths()

from PySide6.QtCore import QLocale

from .translations import DEFAULT_LOCALE, SUPPORTED_LOCALES, TRANSLATIONS


@dataclass(frozen=True)
class Translator:
    locale_name: str

    @classmethod
    def from_system_locale(cls) -> "Translator":
        try:
            system_locale = QLocale.system().name()
        except Exception:
            try:
                system_locale = locale.getlocale()[0] or locale.getdefaultlocale()[0]
            except Exception:
                system_locale = None
        return cls(resolve_locale(system_locale))

    def text(self, key: str) -> str:
        return TRANSLATIONS.get(self.locale_name, TRANSLATIONS[DEFAULT_LOCALE]).get(
            key,
            TRANSLATIONS[DEFAULT_LOCALE].get(key, key),
        )


def resolve_locale(value: str | None) -> str:
    if not value:
        return DEFAULT_LOCALE

    normalized = value.replace("-", "_")
    lower = normalized.lower()
    if lower.startswith("zh"):
        if "cn" in lower or "hans" in lower or lower == "zh":
            return "zh_CN"
    if lower.startswith("ja"):
        return "ja"
    if lower.startswith("en"):
        return "en"

    return DEFAULT_LOCALE if DEFAULT_LOCALE in SUPPORTED_LOCALES else SUPPORTED_LOCALES[0]
