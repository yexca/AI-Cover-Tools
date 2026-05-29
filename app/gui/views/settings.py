from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QColorDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..appearance import AppearanceSettings
from ..i18n import Translator


class SettingsPage(QWidget):
    background_changed = Signal(Path)
    blur_changed = Signal(int)
    text_color_changed = Signal(str)
    tint_color_changed = Signal(str)
    tint_opacity_changed = Signal(int)

    def __init__(self, translator: Translator, appearance: AppearanceSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsPage")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self._translator = translator
        self._appearance = appearance

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
        content.setObjectName("SettingsContent")
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        content.setAutoFillBackground(False)
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(18)

        self._title = QLabel()
        self._title.setObjectName("PageTitle")
        layout.addWidget(self._title)

        background_card = QFrame()
        background_card.setObjectName("GlassCard")
        background_layout = QGridLayout(background_card)
        background_layout.setContentsMargins(18, 16, 18, 16)
        background_layout.setHorizontalSpacing(10)
        background_layout.setVerticalSpacing(12)
        self._background_title = QLabel()
        self._background_title.setObjectName("CardTitle")
        background_layout.addWidget(self._background_title, 0, 0, 1, 3)

        background_row = QHBoxLayout()
        self._background_path = QLabel()
        self._background_path.setObjectName("MutedText")
        self._background_path.setWordWrap(True)
        self._background_button = QPushButton()
        self._background_button.setObjectName("GlassButton")
        self._background_button.clicked.connect(self._choose_background)
        background_row.addWidget(self._background_path, 1)
        background_row.addWidget(self._background_button)
        self._background_label = QLabel()
        background_layout.addWidget(self._background_label, 1, 0)
        background_layout.addLayout(background_row, 1, 1, 1, 2)

        self._blur_slider = QSlider(Qt.Orientation.Horizontal)
        self._blur_slider.setRange(0, 24)
        self._blur_slider.setValue(appearance.blur_radius)
        self._blur_slider.valueChanged.connect(self.blur_changed.emit)
        self._blur_value = QLabel(str(appearance.blur_radius))
        self._blur_slider.valueChanged.connect(lambda value: self._blur_value.setText(str(value)))
        blur_row = QHBoxLayout()
        blur_row.addWidget(self._blur_slider, 1)
        blur_row.addWidget(self._blur_value)
        self._blur_label = QLabel()
        background_layout.addWidget(self._blur_label, 2, 0)
        background_layout.addLayout(blur_row, 2, 1, 1, 2)
        background_layout.setColumnStretch(1, 1)
        layout.addWidget(background_card)

        color_card = QFrame()
        color_card.setObjectName("GlassCard")
        color_layout = QGridLayout(color_card)
        color_layout.setContentsMargins(18, 16, 18, 16)
        color_layout.setHorizontalSpacing(10)
        color_layout.setVerticalSpacing(12)
        self._color_title = QLabel()
        self._color_title.setObjectName("CardTitle")
        color_layout.addWidget(self._color_title, 0, 0, 1, 3)

        self._tint_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._tint_opacity_slider.setRange(0, 220)
        self._tint_opacity_slider.setValue(appearance.tint_opacity)
        self._tint_opacity_slider.valueChanged.connect(self.tint_opacity_changed.emit)
        self._tint_opacity_value = QLabel(str(appearance.tint_opacity))
        self._tint_opacity_slider.valueChanged.connect(lambda value: self._tint_opacity_value.setText(str(value)))
        tint_opacity_row = QHBoxLayout()
        tint_opacity_row.addWidget(self._tint_opacity_slider, 1)
        tint_opacity_row.addWidget(self._tint_opacity_value)
        self._tint_opacity_label = QLabel()
        color_layout.addWidget(self._tint_opacity_label, 1, 0)
        color_layout.addLayout(tint_opacity_row, 1, 1, 1, 2)

        tint_color_row = QHBoxLayout()
        self._tint_color_preview = QLabel()
        self._tint_color_preview.setObjectName("ColorPreview")
        self._tint_color_preview.setFixedSize(28, 28)
        self._tint_color_button = QPushButton()
        self._tint_color_button.setObjectName("GlassButton")
        self._tint_color_button.clicked.connect(self._choose_tint_color)
        tint_color_row.addWidget(self._tint_color_preview)
        tint_color_row.addWidget(self._tint_color_button)
        tint_color_row.addStretch(1)
        self._tint_color_label = QLabel()
        color_layout.addWidget(self._tint_color_label, 2, 0)
        color_layout.addLayout(tint_color_row, 2, 1, 1, 2)

        color_row = QHBoxLayout()
        self._color_preview = QLabel()
        self._color_preview.setObjectName("ColorPreview")
        self._color_preview.setFixedSize(28, 28)
        self._color_button = QPushButton()
        self._color_button.setObjectName("GlassButton")
        self._color_button.clicked.connect(self._choose_text_color)
        color_row.addWidget(self._color_preview)
        color_row.addWidget(self._color_button)
        color_row.addStretch(1)
        self._color_label = QLabel()
        color_layout.addWidget(self._color_label, 3, 0)
        color_layout.addLayout(color_row, 3, 1, 1, 2)
        color_layout.setColumnStretch(1, 1)
        layout.addWidget(color_card)

        layout.addStretch(1)
        self.retranslate(translator)
        self._refresh_values()

    def retranslate(self, translator: Translator) -> None:
        self._translator = translator
        self._title.setText(translator.text("page.settings.title"))
        self._background_title.setText(translator.text("settings.background_card"))
        self._color_title.setText(translator.text("settings.color_card"))
        self._background_label.setText(translator.text("settings.background"))
        self._background_button.setText(translator.text("settings.choose"))
        self._blur_label.setText(translator.text("settings.blur"))
        self._tint_opacity_label.setText(translator.text("settings.tint_opacity"))
        self._tint_color_label.setText(translator.text("settings.tint_color"))
        self._tint_color_button.setText(translator.text("settings.choose"))
        self._color_label.setText(translator.text("settings.text_color"))
        self._color_button.setText(translator.text("settings.choose"))

    def set_appearance(self, appearance: AppearanceSettings) -> None:
        self._appearance = appearance
        self._blur_slider.blockSignals(True)
        self._blur_slider.setValue(appearance.blur_radius)
        self._blur_slider.blockSignals(False)
        self._tint_opacity_slider.blockSignals(True)
        self._tint_opacity_slider.setValue(appearance.tint_opacity)
        self._tint_opacity_slider.blockSignals(False)
        self._refresh_values()

    def _refresh_values(self) -> None:
        self._background_path.setText(str(self._appearance.background_image))
        self._blur_value.setText(str(self._appearance.blur_radius))
        self._tint_opacity_value.setText(str(self._appearance.tint_opacity))
        self._tint_color_preview.setStyleSheet(
            f"background: {self._appearance.tint_color}; border: 1px solid rgba(255, 255, 255, 0.35); border-radius: 6px;"
        )
        self._color_preview.setStyleSheet(
            f"background: {self._appearance.text_color}; border: 1px solid rgba(255, 255, 255, 0.35); border-radius: 6px;"
        )

    def _choose_background(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self._translator.text("settings.background"),
            str(self._appearance.background_image.parent),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if file_path:
            self.background_changed.emit(Path(file_path))

    def _choose_text_color(self) -> None:
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            self.text_color_changed.emit(color.name())

    def _choose_tint_color(self) -> None:
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            self.tint_color_changed.emit(color.name())
