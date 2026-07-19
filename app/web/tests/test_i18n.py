from __future__ import annotations

import re
import unittest
from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
LOCALES_DIR = STATIC_DIR / "i18n" / "locales"


def locale_keys(name: str) -> set[str]:
    source = (LOCALES_DIR / name).read_text(encoding="utf-8")
    return set(re.findall(r"^\s*'([^']+)'\s*:", source, flags=re.MULTILINE))


class I18nTests(unittest.TestCase):
    def test_locale_dictionaries_have_identical_keys(self) -> None:
        english = locale_keys("en.js")
        self.assertGreater(len(english), 200)
        self.assertEqual(locale_keys("zh-CN.js"), english)
        self.assertEqual(locale_keys("ja.js"), english)

    def test_static_literal_references_exist_in_every_locale(self) -> None:
        english = locale_keys("en.js")
        app_source = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        index_source = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        call_keys = set(re.findall(r"\b(?:t|plural)\(\s*'([^']+)'", app_source))
        attribute_keys = set(
            re.findall(r'data-i18n(?:-placeholder|-title|-aria-label)?="([^"]+)"', index_source)
        )
        referenced = call_keys | attribute_keys
        missing = sorted(key for key in referenced if key not in english and f"{key}.other" not in english)
        self.assertEqual(missing, [])

    def test_language_scripts_load_before_the_application(self) -> None:
        source = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        positions = [
            source.index('/i18n/locales/en.js'),
            source.index('/i18n/locales/zh-CN.js'),
            source.index('/i18n/locales/ja.js'),
            source.index('/i18n/core.js'),
            source.index('/app.js'),
        ]
        self.assertEqual(positions, sorted(positions))

    def test_frontend_preserves_raw_model_stems_as_port_handles(self) -> None:
        source = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("return { id: item, label: item }", source)
        self.assertNotIn("id: item.toLowerCase().replace", source)


if __name__ == "__main__":
    unittest.main()
