from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEasingCurve, Property, QSize, QPropertyAnimation, Signal
from PySide6.QtGui import QPainter, QPixmap, QTransform
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..icons import svg_icon
from ..i18n import Translator


@dataclass(frozen=True)
class NavigationItem:
    key: str
    text_key: str
    icon_name: str


LANGUAGE_OPTIONS = (
    ("zh_CN", "简体中文"),
    ("en", "English"),
    ("ja", "日本語"),
)


class NavigationButton(QPushButton):
    def __init__(self, item: NavigationItem, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item = item
        self._translator = translator
        self._expanded = True
        self._icon_angle = 0.0
        self._base_pixmap = svg_icon(item.icon_name, "#f7f9fc", 24).pixmap(QSize(24, 24))
        self._animation = QPropertyAnimation(self, b"iconAngle", self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setCheckable(True)
        self.setCursor(QtCursor.pointing_hand())
        self.setIconSize(QSize(20, 20))
        self.setMinimumHeight(42)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._update_icon()
        self.refresh_text()

    def enterEvent(self, event) -> None:  # noqa: ANN001
        self._animate_icon(8.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self._animate_icon(0.0 if not self.isChecked() else -6.0)
        super().leaveEvent(event)

    def nextCheckState(self) -> None:
        super().nextCheckState()
        self._animate_icon(-6.0 if self.isChecked() else 0.0)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.refresh_text()

    def refresh_text(self) -> None:
        label = self._translator.text(self.item.text_key)
        self.setToolTip(label)
        self.setText(label if self._expanded else "")

    def icon_angle(self) -> float:
        return self._icon_angle

    def set_icon_angle(self, value: float) -> None:
        self._icon_angle = value
        self._update_icon()

    iconAngle = Property(float, icon_angle, set_icon_angle)

    def _animate_icon(self, angle: float) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._icon_angle)
        self._animation.setEndValue(angle)
        self._animation.start()

    def _update_icon(self) -> None:
        canvas = QPixmap(self._base_pixmap.size())
        canvas.fill(QtCursor.transparent())
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        center = canvas.rect().center()
        transform = QTransform()
        transform.translate(center.x(), center.y())
        transform.rotate(self._icon_angle)
        transform.translate(-center.x(), -center.y())
        painter.setTransform(transform)
        painter.drawPixmap(0, 0, self._base_pixmap)
        painter.end()
        self.setIcon(canvas)


class NavigationRail(QFrame):
    page_selected = Signal(str)
    language_changed = Signal(str)

    def __init__(self, items: list[NavigationItem], translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items = items
        self._translator = translator
        self._expanded = True
        self._buttons: dict[str, NavigationButton] = {}
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._language_combo: QComboBox | None = None

        self.setObjectName("NavigationRail")
        self.setMinimumWidth(84)
        self.setMaximumWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        self._title = QLabel(self._translator.text("app.title"))
        self._title.setObjectName("AppTitle")
        self._collapse_button = QToolButton()
        self._collapse_button.setObjectName("IconButton")
        self._collapse_button.setCursor(QtCursor.pointing_hand())
        self._collapse_button.setIcon(svg_icon("chevron-left"))
        self._collapse_button.clicked.connect(self.toggle_expanded)
        header.addWidget(self._title, 1)
        header.addWidget(self._collapse_button)
        layout.addLayout(header)

        subtitle = QLabel(self._translator.text("app.subtitle"))
        subtitle.setObjectName("AppSubtitle")
        subtitle.setWordWrap(True)
        self._subtitle = subtitle
        layout.addWidget(subtitle)
        layout.addSpacing(10)

        for item in self._items:
            button = NavigationButton(item, self._translator)
            button.clicked.connect(lambda checked=False, key=item.key: self.page_selected.emit(key))
            self._buttons[item.key] = button
            self._button_group.addButton(button)
            layout.addWidget(button)

        layout.addStretch(1)

        language_row = QHBoxLayout()
        language_row.setSpacing(8)
        self._language_icon = QLabel()
        self._language_icon.setPixmap(svg_icon("language", "#f7f9fc", 20).pixmap(QSize(20, 20)))
        self._language_icon.setToolTip(self._translator.text("nav.language"))
        self._language_combo = QComboBox()
        self._language_combo.setObjectName("LanguageCombo")
        self._language_combo.setToolTip(self._translator.text("nav.language"))
        for locale_name, label in LANGUAGE_OPTIONS:
            self._language_combo.addItem(label, locale_name)
        self._language_combo.currentIndexChanged.connect(self._emit_language_changed)
        language_row.addWidget(self._language_icon)
        language_row.addWidget(self._language_combo, 1)
        layout.addLayout(language_row)

    def set_current(self, key: str) -> None:
        button = self._buttons.get(key)
        if button:
            button.setChecked(True)
            button._animate_icon(-6.0)

    def set_locale(self, locale_name: str) -> None:
        if not self._language_combo:
            return
        index = self._language_combo.findData(locale_name)
        if index >= 0:
            blocked = self._language_combo.blockSignals(True)
            self._language_combo.setCurrentIndex(index)
            self._language_combo.blockSignals(blocked)

    def retranslate(self, translator: Translator) -> None:
        self._translator = translator
        self._title.setText(translator.text("app.title"))
        self._subtitle.setText(translator.text("app.subtitle"))
        self._collapse_button.setToolTip(translator.text("nav.collapse" if self._expanded else "nav.expand"))
        self._language_icon.setToolTip(translator.text("nav.language"))
        if self._language_combo:
            self._language_combo.setToolTip(translator.text("nav.language"))
        for button in self._buttons.values():
            button._translator = translator
            button.refresh_text()

    def toggle_expanded(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.setFixedWidth(220 if expanded else 84)
        self._title.setVisible(expanded)
        self._subtitle.setVisible(expanded)
        self._collapse_button.setToolTip(self._translator.text("nav.collapse" if expanded else "nav.expand"))
        self._collapse_button.setIcon(svg_icon("chevron-left" if expanded else "chevron-right"))
        if self._language_combo:
            self._language_combo.setVisible(expanded)
        for button in self._buttons.values():
            button.set_expanded(expanded)

    def _emit_language_changed(self) -> None:
        if self._language_combo:
            self.language_changed.emit(str(self._language_combo.currentData()))


class QtCursor:
    @staticmethod
    def pointing_hand():
        from PySide6.QtCore import Qt

        return Qt.CursorShape.PointingHandCursor

    @staticmethod
    def transparent():
        from PySide6.QtCore import Qt

        return Qt.GlobalColor.transparent
