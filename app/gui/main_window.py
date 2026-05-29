from __future__ import annotations

from .bootstrap import configure_windows_dll_paths

configure_windows_dll_paths()

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout

from .appearance import AppearanceSettings
from .i18n import Translator
from .style import build_style
from .views import PlaceholderPage, SeparatePage, SettingsPage, SlicerPage, ToolsPage
from .widgets import BackgroundWidget, BlurLayer, NavigationItem, NavigationRail, TintLayer


class MainWindow(QMainWindow):
    def __init__(self, translator: Translator) -> None:
        super().__init__()
        self._translator = translator
        self._pages: dict[str, int] = {}
        self._page_widgets: list[PlaceholderPage | SeparatePage | SettingsPage | SlicerPage | ToolsPage] = []
        self._appearance = AppearanceSettings()

        self.setWindowTitle(translator.text("app.title"))
        self.resize(1180, 760)
        self.setMinimumSize(900, 560)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet(build_style(self._appearance.text_color))

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.black)
        self.setPalette(palette)

        background = BackgroundWidget(self._appearance.background_image)
        blur_layer = BlurLayer(self._appearance.blur_radius, parent=background)
        if self._appearance.background_image.exists():
            blur_layer.setPixmap(QPixmap(str(self._appearance.background_image)))
        blur_layer.lower()
        tint_color = QColor(self._appearance.tint_color)
        tint_color.setAlpha(self._appearance.tint_opacity)
        tint_layer = TintLayer(tint_color, parent=background)

        root_layout = QVBoxLayout(background)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        main_layout = QHBoxLayout()
        main_layout.setSpacing(12)
        root_layout.addLayout(main_layout, 1)

        self._nav = NavigationRail(self._navigation_items(), translator)
        self._nav.set_expanded(False)
        self._nav.set_locale(translator.locale_name)
        self._nav.page_selected.connect(self._show_page)
        self._nav.language_changed.connect(self._change_language)
        main_layout.addWidget(self._nav)

        content_panel = QFrame()
        content_panel.setObjectName("ContentPanel")
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()
        content_layout.addWidget(self._stack)
        main_layout.addWidget(content_panel, 1)

        self.setCentralWidget(background)
        self._background = background
        self._blur_layer = blur_layer
        self._tint_layer = tint_layer
        self.statusBar().showMessage(translator.text("status.ready"))

        self._add_pages()
        self._show_page("home")

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        if hasattr(self, "_blur_layer"):
            self._blur_layer.setGeometry(self._background.rect())
            self._tint_layer.setGeometry(self._background.rect())

    def _navigation_items(self) -> list[NavigationItem]:
        return [
            NavigationItem("home", "nav.home", "home"),
            NavigationItem("separate", "nav.separate", "separate"),
            NavigationItem("slicer", "nav.slicer", "slicer"),
            NavigationItem("train", "nav.train", "train"),
            NavigationItem("inference", "nav.inference", "inference"),
            NavigationItem("tools", "nav.tools", "tools"),
            NavigationItem("settings", "nav.settings", "settings"),
            NavigationItem("about", "nav.about", "about"),
        ]

    def _add_pages(self) -> None:
        for key in ("home", "train", "inference", "about"):
            page = PlaceholderPage(f"page.{key}.title", f"page.{key}.body", self._translator)
            self._page_widgets.append(page)
            self._pages[key] = self._stack.addWidget(page)

        separate_page = SeparatePage(self._translator)
        separate_page.status_changed.connect(self.statusBar().showMessage)
        self._page_widgets.append(separate_page)
        self._pages["separate"] = self._stack.addWidget(separate_page)

        slicer_page = SlicerPage(self._translator)
        slicer_page.status_changed.connect(self.statusBar().showMessage)
        self._page_widgets.append(slicer_page)
        self._pages["slicer"] = self._stack.addWidget(slicer_page)

        tools_page = ToolsPage(self._translator)
        tools_page.status_changed.connect(self.statusBar().showMessage)
        self._page_widgets.append(tools_page)
        self._pages["tools"] = self._stack.addWidget(tools_page)

        settings_page = SettingsPage(self._translator, self._appearance)
        settings_page.background_changed.connect(self._set_background_image)
        settings_page.blur_changed.connect(self._set_blur_radius)
        settings_page.text_color_changed.connect(self._set_text_color)
        settings_page.tint_color_changed.connect(self._set_tint_color)
        settings_page.tint_opacity_changed.connect(self._set_tint_opacity)
        self._settings_page = settings_page
        self._page_widgets.append(settings_page)
        self._pages["settings"] = self._stack.addWidget(settings_page)

    def _show_page(self, key: str) -> None:
        index = self._pages.get(key)
        if index is None:
            return
        self._stack.setCurrentIndex(index)
        self._nav.set_current(key)

    def _change_language(self, locale_name: str) -> None:
        self._translator = Translator(locale_name)
        self.setWindowTitle(self._translator.text("app.title"))
        self._nav.retranslate(self._translator)
        for page in self._page_widgets:
            page.retranslate(self._translator)
        self.statusBar().showMessage(self._translator.text("status.ready"))

    def _set_background_image(self, image_path) -> None:  # noqa: ANN001
        self._appearance.background_image = image_path
        self._background.set_image(image_path)
        self._blur_layer.setPixmap(QPixmap(str(image_path)))
        self._settings_page.set_appearance(self._appearance)

    def _set_blur_radius(self, blur_radius: int) -> None:
        self._appearance.blur_radius = blur_radius
        self._blur_layer.set_blur_radius(blur_radius)
        self._settings_page.set_appearance(self._appearance)

    def _set_text_color(self, text_color: str) -> None:
        self._appearance.text_color = text_color
        self.setStyleSheet(build_style(text_color))
        self._settings_page.set_appearance(self._appearance)

    def _set_tint_color(self, tint_color: str) -> None:
        self._appearance.tint_color = tint_color
        color = QColor(tint_color)
        color.setAlpha(self._appearance.tint_opacity)
        self._tint_layer.set_color(color)
        self._settings_page.set_appearance(self._appearance)

    def _set_tint_opacity(self, opacity: int) -> None:
        self._appearance.tint_opacity = opacity
        self._tint_layer.set_opacity(opacity)
        self._settings_page.set_appearance(self._appearance)
