from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from ..i18n import Translator


class HomePage(QWidget):
    page_requested = Signal(str)

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomePage")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self._translator = translator

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setObjectName("TransparentScrollArea")
        scroll.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        scroll.setAutoFillBackground(False)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        scroll.viewport().setAutoFillBackground(False)
        root.addWidget(scroll)

        content = QWidget()
        content.setObjectName("HomeContent")
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        content.setAutoFillBackground(False)
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(16)

        self._title = QLabel()
        self._title.setObjectName("PageTitle")
        layout.addWidget(self._title)

        self._intro_title, self._intro_body, self._intro_card = self._make_card()
        layout.addWidget(self._intro_card)

        self._scope_title, self._scope_body, self._scope_card = self._make_card()
        layout.addWidget(self._scope_card)

        self._flow_title, self._flow_body, self._flow_card = self._make_flow_card()
        layout.addWidget(self._flow_card)

        self._separate_title, self._separate_body, self._separate_card = self._make_card("separate")
        layout.addWidget(self._separate_card)

        self._slicer_title, self._slicer_body, self._slicer_card = self._make_card("slicer")
        layout.addWidget(self._slicer_card)

        self._tools_title, self._tools_body, self._tools_card = self._make_card("tools")
        layout.addWidget(self._tools_card)

        self._more_title, self._more_body, self._more_card = self._make_card("about")
        layout.addWidget(self._more_card)

        layout.addStretch(1)
        self.retranslate(translator)

    def retranslate(self, translator: Translator) -> None:
        self._translator = translator
        self._title.setText(translator.text("page.home.title"))

        self._intro_title.setText(translator.text("home.intro.title"))
        self._intro_body.setText(translator.text("home.intro.body"))
        self._scope_title.setText(translator.text("home.scope.title"))
        self._scope_body.setText(translator.text("home.scope.body"))
        self._flow_title.setText(translator.text("home.flow.title"))
        self._flow_body.setText(translator.text("home.flow.note"))
        self._separate_title.setText(translator.text("home.separate.title"))
        self._separate_body.setText(translator.text("home.separate.body"))
        self._slicer_title.setText(translator.text("home.slicer.title"))
        self._slicer_body.setText(translator.text("home.slicer.body"))
        self._tools_title.setText(translator.text("home.tools.title"))
        self._tools_body.setText(translator.text("home.tools.body"))
        self._more_title.setText(translator.text("home.more.title"))
        self._more_body.setText(translator.text("home.more.body"))

        flow_keys = ("home.flow.extract", "home.flow.slice", "home.flow.train", "home.flow.inference")
        for label, key in zip(self._flow_steps, flow_keys, strict=True):
            label.setText(translator.text(key))

        for key, button in self._buttons.items():
            button.setText(translator.text(f"home.open_{key}"))

    def _make_card(self, target_page: str | None = None) -> tuple[QLabel, QLabel, QFrame]:
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel()
        title.setObjectName("CardTitle")
        body = QLabel()
        body.setObjectName("PageBody")
        body.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(body)

        if target_page is not None:
            row = QHBoxLayout()
            row.addStretch(1)
            button = QPushButton()
            button.setObjectName("GlassButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, page=target_page: self.page_requested.emit(page))
            row.addWidget(button)
            layout.addLayout(row)
            self._buttons = getattr(self, "_buttons", {})
            self._buttons[target_page] = button

        return title, body, card

    def _make_flow_card(self) -> tuple[QLabel, QLabel, QFrame]:
        title, body, card = self._make_card()
        layout = card.layout()
        if not isinstance(layout, QVBoxLayout):
            return title, body, card

        flow_row = QHBoxLayout()
        flow_row.setSpacing(8)
        self._flow_steps: list[QLabel] = []
        for index in range(4):
            step = QLabel()
            step.setObjectName("FlowStepMuted" if index >= 2 else "FlowStep")
            step.setAlignment(Qt.AlignmentFlag.AlignCenter)
            step.setMinimumHeight(34)
            step.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._flow_steps.append(step)
            flow_row.addWidget(step)
            if index < 3:
                arrow = QLabel(">")
                arrow.setObjectName("MutedText")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                flow_row.addWidget(arrow)
        layout.insertLayout(1, flow_row)
        return title, body, card
