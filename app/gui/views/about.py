from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from ..i18n import Translator


BLOG_URLS = {
    "zh_CN": "https://blog.yexca.net/archives/283/",
    "en": "https://blog.yexca.net/en/archives/283/",
    "ja": "https://blog.yexca.net/ja/archives/283/",
}

AUTHOR_URL = "https://yexca.net"

CREDIT_LINKS = (
    ("about.credit.shnva", "about.credit.shnva.purpose", "https://www.pixiv.net/artworks/76371065"),
    ("about.credit.applio", "about.credit.applio.purpose", "https://github.com/IAHispano/Applio"),
    ("about.credit.msst_gui", "about.credit.msst_gui.purpose", "https://github.com/AliceNavigator/Music-Source-Separation-Training-GUI"),
    ("about.credit.spek", "about.credit.spek.purpose", "https://github.com/alexkay/spek"),
)

DEPENDENCY_LINKS = (
    ("about.dependency.audio_separator", "about.dependency.audio_separator.purpose", "https://github.com/nomadkaraoke/python-audio-separator"),
    ("about.dependency.pyside6", "about.dependency.pyside6.purpose", "https://pyside.org"),
    ("about.dependency.ffmpeg", "about.dependency.ffmpeg.purpose", "https://ffmpeg.org"),
    ("about.dependency.pytorch", "about.dependency.pytorch.purpose", "https://pytorch.org"),
    ("about.dependency.numpy", "about.dependency.numpy.purpose", "https://numpy.org"),
    ("about.dependency.scipy", "about.dependency.scipy.purpose", "https://scipy.org"),
    ("about.dependency.soundfile", "about.dependency.soundfile.purpose", "https://github.com/bastibe/python-soundfile"),
    ("about.dependency.libsndfile", "about.dependency.libsndfile.purpose", "https://libsndfile.github.io/libsndfile/"),
    ("about.dependency.pillow", "about.dependency.pillow.purpose", "https://python-pillow.github.io"),
    ("about.dependency.parselmouth", "about.dependency.parselmouth.purpose", "https://github.com/YannickJadoul/Parselmouth"),
    ("about.dependency.ffmpeg_normalize", "about.dependency.ffmpeg_normalize.purpose", "https://github.com/slhck/ffmpeg-normalize"),
)


class AboutPage(QWidget):
    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AboutPage")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self._translator = translator
        self._credit_rows: list[tuple[QLabel, QLabel, QPushButton]] = []
        self._dependency_rows: list[tuple[QLabel, QLabel, QPushButton]] = []

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
        content.setObjectName("AboutContent")
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
        self._blog_grid = QFrame()
        self._blog_grid.setObjectName("TransparentFrame")
        blog_layout = QGridLayout(self._blog_grid)
        blog_layout.setContentsMargins(0, 6, 0, 0)
        blog_layout.setHorizontalSpacing(12)
        blog_layout.setVerticalSpacing(8)
        self._blog_label = QLabel()
        self._blog_label.setObjectName("LinkName")
        self._blog_purpose = QLabel()
        self._blog_purpose.setObjectName("MutedText")
        self._blog_purpose.setWordWrap(True)
        self._blog_button = self._make_link_button("", BLOG_URLS[translator.locale_name])
        blog_layout.addWidget(self._blog_label, 0, 0)
        blog_layout.addWidget(self._blog_purpose, 0, 1)
        blog_layout.addWidget(self._blog_button, 0, 2)
        blog_layout.setColumnStretch(1, 1)
        self._intro_card.layout().addWidget(self._blog_grid)
        layout.addWidget(self._intro_card)

        self._development_title, self._development_body, self._development_card = self._make_card()
        author_row = QHBoxLayout()
        author_row.addStretch(1)
        self._author_button = self._make_link_button("", AUTHOR_URL)
        author_row.addWidget(self._author_button)
        self._development_card.layout().addItem(author_row)
        layout.addWidget(self._development_card)

        self._credits_title, self._credits_body, self._credits_card = self._make_card()
        self._credits_grid = self._make_link_grid(CREDIT_LINKS, self._credit_rows)
        self._credits_card.layout().addWidget(self._credits_grid)
        layout.addWidget(self._credits_card)

        self._dependencies_title, self._dependencies_body, self._dependencies_card = self._make_card()
        self._dependencies_grid = self._make_link_grid(DEPENDENCY_LINKS, self._dependency_rows)
        self._dependencies_card.layout().addWidget(self._dependencies_grid)
        layout.addWidget(self._dependencies_card)

        layout.addStretch(1)
        self.retranslate(translator)

    def retranslate(self, translator: Translator) -> None:
        self._translator = translator
        self._title.setText(translator.text("page.about.title"))
        self._intro_title.setText(translator.text("about.intro.title"))
        self._intro_body.setText(translator.text("about.intro.body"))
        self._development_title.setText(translator.text("about.development.title"))
        self._development_body.setText(translator.text("about.development.body"))
        self._credits_title.setText(translator.text("about.credits.title"))
        self._credits_body.setText(translator.text("about.credits.body"))
        self._dependencies_title.setText(translator.text("about.dependencies.title"))
        self._dependencies_body.setText(translator.text("about.dependencies.body"))
        self._author_button.setText(translator.text("about.author"))
        self._blog_label.setText(translator.text("about.blog.article"))
        self._blog_purpose.setText(translator.text("about.blog.purpose"))
        self._blog_button.setText(translator.text("about.open_link"))
        self._set_link_button_url(self._blog_button, BLOG_URLS.get(translator.locale_name, BLOG_URLS["en"]))

        self._retranslate_rows(CREDIT_LINKS, self._credit_rows, translator)
        self._retranslate_rows(DEPENDENCY_LINKS, self._dependency_rows, translator)

    def _make_card(self) -> tuple[QLabel, QLabel, QFrame]:
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
        return title, body, card

    def _make_link_grid(self, links: tuple[tuple[str, str, str], ...], rows: list[tuple[QLabel, QLabel, QPushButton]]) -> QFrame:
        frame = QFrame()
        frame.setObjectName("TransparentFrame")
        grid = QGridLayout(frame)
        grid.setContentsMargins(0, 6, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        for row_index, (_, _, url) in enumerate(links):
            name = QLabel()
            name.setObjectName("LinkName")
            purpose = QLabel()
            purpose.setObjectName("MutedText")
            purpose.setWordWrap(True)
            button = self._make_link_button("", url)
            grid.addWidget(name, row_index, 0)
            grid.addWidget(purpose, row_index, 1)
            grid.addWidget(button, row_index, 2)
            rows.append((name, purpose, button))

        grid.setColumnStretch(1, 1)
        return frame

    def _make_link_button(self, text: str, url: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("GlassButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(self._open_link_button_url)
        self._set_link_button_url(button, url)
        return button

    def _set_link_button_url(self, button: QPushButton, url: str) -> None:
        button.setProperty("link_url", url)
        button.setToolTip(url)

    def _open_link_button_url(self) -> None:
        button = self.sender()
        if isinstance(button, QPushButton):
            url = str(button.property("link_url") or "")
            if url:
                QDesktopServices.openUrl(QUrl(url))

    def _retranslate_rows(
        self,
        links: tuple[tuple[str, str, str], ...],
        rows: list[tuple[QLabel, QLabel, QPushButton]],
        translator: Translator,
    ) -> None:
        for (name_key, purpose_key, _), (name, purpose, button) in zip(links, rows, strict=True):
            name.setText(translator.text(name_key))
            purpose.setText(translator.text(purpose_key))
            button.setText(translator.text("about.open_link"))
