from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..i18n import Translator


class PlaceholderPage(QWidget):
    def __init__(self, title_key: str, body_key: str, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title_key = title_key
        self._body_key = body_key
        self._translator = translator
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(14)

        self._title = QLabel()
        self._title.setObjectName("PageTitle")

        self._body = QLabel()
        self._body.setObjectName("PageBody")
        self._body.setWordWrap(True)

        layout.addWidget(self._title)
        layout.addWidget(self._body)
        layout.addStretch(1)
        self.retranslate(translator)

    def retranslate(self, translator: Translator) -> None:
        self._translator = translator
        self._title.setText(translator.text(self._title_key))
        self._body.setText(translator.text(self._body_key))
