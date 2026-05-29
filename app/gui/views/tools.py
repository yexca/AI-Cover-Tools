from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...tools import AudioQualityResult, DurationSummary, NormalizeResult, PitchReport
from ...tools import analyze_audio_quality, analyze_dataset_pitch, calculate_total_duration, normalize_audio_directory
from ..i18n import Translator
from ..paths import PROJECT_ROOT
from ..widgets import WheelDisabledDoubleSpinBox


class DropArea(QFrame):
    path_dropped = Signal(str)

    def __init__(self, accept_folder: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DropArea")
        self.setAcceptDrops(True)
        self._accept_folder = accept_folder
        self._label = QLabel()
        self._label.setObjectName("MutedText")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 18, 14, 18)
        layout.addWidget(self._label)

    def set_text(self, text: str) -> None:
        self._label.setText(text)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._first_supported_path(event.mimeData().urls()) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        path = self._first_supported_path(event.mimeData().urls())
        if path is None:
            event.ignore()
            return
        self.path_dropped.emit(str(path))
        event.acceptProposedAction()

    def _first_supported_path(self, urls: list[QUrl]) -> Path | None:
        for url in urls:
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if self._accept_folder and path.is_dir():
                    return path
                if not self._accept_folder and path.is_file():
                    return path
        return None


class PreviewImageLabel(QLabel):
    preview_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image_path: Path | None = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_image_path(self, image_path: Path | None) -> None:
        self._image_path = image_path

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.MouseButton.LeftButton and self._image_path is not None:
            self.preview_requested.emit(self._image_path)
            return
        super().mousePressEvent(event)


class ToolWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        mode: str,
        path: Path,
        output_path: Path | None = None,
        target_peak_db: float = -3.0,
        pitch_algorithm: str = "praat",
    ) -> None:
        super().__init__()
        self._mode = mode
        self._path = path
        self._output_path = output_path
        self._target_peak_db = target_peak_db
        self._pitch_algorithm = pitch_algorithm

    @Slot()
    def run(self) -> None:
        try:
            if self._mode == "quality":
                result = analyze_audio_quality(self._path, PROJECT_ROOT / "outputs")
            elif self._mode == "duration":
                result = calculate_total_duration(self._path)
            elif self._mode == "pitch":
                result = analyze_dataset_pitch(self._path, PROJECT_ROOT / "outputs", algorithm=self._pitch_algorithm)
            elif self._mode == "normalize":
                if self._output_path is None:
                    raise ValueError("output_path")
                result = normalize_audio_directory(self._path, self._output_path, self._target_peak_db)
            else:
                raise ValueError(self._mode)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__)


class ToolsPage(QWidget):
    status_changed = Signal(str)

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ToolsPage")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self._translator = translator
        self._thread: QThread | None = None
        self._worker: ToolWorker | None = None
        self._current_mode = "quality"
        self._quality_result: AudioQualityResult | None = None
        self._quality_segment_index = 0
        self._pitch_plot_path: Path | None = None

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
        content.setObjectName("ToolsContent")
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        content.setAutoFillBackground(False)
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(16)

        self._title = QLabel()
        self._title.setObjectName("PageTitle")
        layout.addWidget(self._title)

        self._selector_card = QFrame()
        self._selector_card.setObjectName("GlassCard")
        selector_layout = QHBoxLayout(self._selector_card)
        selector_layout.setContentsMargins(18, 16, 18, 16)
        selector_layout.setSpacing(10)
        self._selector_title = QLabel()
        self._selector_title.setObjectName("CardTitle")
        selector_layout.addWidget(self._selector_title)
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._quality_button = self._create_selector_button("quality", 0)
        self._duration_button = self._create_selector_button("duration", 1)
        self._pitch_button = self._create_selector_button("pitch", 2)
        self._normalize_button = self._create_selector_button("normalize", 3)
        selector_layout.addWidget(self._quality_button)
        selector_layout.addWidget(self._duration_button)
        selector_layout.addWidget(self._pitch_button)
        selector_layout.addWidget(self._normalize_button)
        selector_layout.addStretch(1)
        layout.addWidget(self._selector_card)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_quality_page())
        self._stack.addWidget(self._build_duration_page())
        self._stack.addWidget(self._build_pitch_page())
        self._stack.addWidget(self._build_normalize_page())
        layout.addWidget(self._stack)
        layout.addStretch(1)

        self._button_group.idClicked.connect(self._switch_tool)
        self._quality_button.setChecked(True)
        self.retranslate(translator)

    def retranslate(self, translator: Translator) -> None:
        self._translator = translator
        self._title.setText(translator.text("page.tools.title"))
        self._selector_title.setText(translator.text("tools.selector"))
        self._quality_button.setText(translator.text("tools.quality"))
        self._duration_button.setText(translator.text("tools.duration"))
        self._pitch_button.setText(translator.text("tools.pitch"))
        self._normalize_button.setText(translator.text("tools.normalize"))

        self._quality_input_title.setText(translator.text("tools.input"))
        self._quality_output_title.setText(translator.text("tools.output"))
        self._quality_file_label.setText(translator.text("tools.audio_file"))
        self._quality_choose.setText(translator.text("settings.choose"))
        self._quality_run.setText(translator.text("tools.view"))
        self._drop_area.set_text(translator.text("tools.drop_audio"))
        self._quality_prev.setText(translator.text("tools.previous_segment"))
        self._quality_next.setText(translator.text("tools.next_segment"))
        self._quality_output_card.setVisible(self._quality_result is not None)

        self._duration_input_title.setText(translator.text("tools.input"))
        self._duration_output_title.setText(translator.text("tools.output"))
        self._duration_folder_label.setText(translator.text("tools.folder"))
        self._duration_choose.setText(translator.text("settings.choose"))
        self._duration_run.setText(translator.text("tools.calculate"))
        self._duration_drop_area.set_text(translator.text("tools.drop_folder"))
        self._duration_output_card.setVisible(bool(self._duration_text.text()))

        self._pitch_input_title.setText(translator.text("tools.input"))
        self._pitch_output_title.setText(translator.text("tools.output"))
        self._pitch_folder_label.setText(translator.text("tools.folder"))
        self._pitch_algorithm_label.setText(translator.text("tools.pitch.algorithm"))
        self._pitch_choose.setText(translator.text("settings.choose"))
        self._pitch_run.setText(translator.text("tools.analyze"))
        self._pitch_drop_area.set_text(translator.text("tools.drop_folder"))
        self._pitch_output_card.setVisible(bool(self._pitch_text.toPlainText()))

        self._normalize_input_title.setText(translator.text("tools.input"))
        self._normalize_output_title.setText(translator.text("tools.output"))
        self._normalize_input_label.setText(translator.text("tools.input_folder"))
        self._normalize_input_choose.setText(translator.text("settings.choose"))
        self._normalize_input_drop_area.set_text(translator.text("tools.drop_input_folder"))
        self._normalize_output_label.setText(translator.text("tools.output_folder"))
        self._normalize_output_choose.setText(translator.text("settings.choose"))
        self._normalize_output_drop_area.set_text(translator.text("tools.drop_output_folder"))
        self._normalize_peak_label.setText(translator.text("tools.target_peak"))
        self._normalize_run.setText(translator.text("tools.normalize.run"))
        self._normalize_output_card.setVisible(bool(self._normalize_text.text()))

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._refresh_output_images()

    def _create_selector_button(self, mode: str, button_id: int) -> QPushButton:
        button = QPushButton()
        button.setObjectName("SegmentButton")
        button.setCheckable(True)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        button.setProperty("mode", mode)
        self._button_group.addButton(button, button_id)
        return button

    def _build_quality_page(self) -> QWidget:
        page = QWidget()
        page.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        page.setAutoFillBackground(False)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        input_card = QFrame()
        input_card.setObjectName("GlassCard")
        input_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        input_layout = QGridLayout(input_card)
        input_layout.setContentsMargins(18, 16, 18, 16)
        input_layout.setHorizontalSpacing(10)
        input_layout.setVerticalSpacing(12)
        self._quality_input_title = QLabel()
        self._quality_input_title.setObjectName("CardTitle")
        self._quality_file_label = QLabel()
        self._quality_path = QLineEdit()
        self._quality_choose = QPushButton()
        self._quality_choose.setObjectName("GlassButton")
        self._quality_choose.clicked.connect(self._choose_audio_file)
        self._quality_run = QPushButton()
        self._quality_run.setObjectName("PrimaryButton")
        self._quality_run.clicked.connect(self._start_quality)
        self._drop_area = DropArea()
        self._drop_area.path_dropped.connect(self._quality_path.setText)
        input_layout.addWidget(self._quality_input_title, 0, 0, 1, 3)
        input_layout.addWidget(self._quality_file_label, 1, 0)
        input_layout.addWidget(self._quality_path, 1, 1)
        input_layout.addWidget(self._quality_choose, 1, 2)
        input_layout.addWidget(self._drop_area, 2, 0, 1, 3)
        input_layout.addWidget(self._quality_run, 3, 2)
        input_layout.setColumnStretch(1, 1)
        layout.addWidget(input_card)

        self._quality_output_card = QFrame()
        self._quality_output_card.setObjectName("GlassCard")
        self._quality_output_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        output_layout = QVBoxLayout(self._quality_output_card)
        output_layout.setContentsMargins(18, 16, 18, 16)
        output_layout.setSpacing(12)
        self._quality_output_title = QLabel()
        self._quality_output_title.setObjectName("CardTitle")
        self._quality_meta = QLabel()
        self._quality_meta.setObjectName("MutedText")
        self._quality_image = PreviewImageLabel()
        self._quality_image.setObjectName("SpectrogramImage")
        self._quality_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._quality_image.setMinimumHeight(520)
        self._quality_image.setScaledContents(False)
        self._quality_image.preview_requested.connect(self._open_image_preview)
        nav = QHBoxLayout()
        self._quality_prev = QPushButton()
        self._quality_prev.setObjectName("GlassButton")
        self._quality_prev.clicked.connect(lambda: self._show_quality_segment(self._quality_segment_index - 1))
        self._quality_next = QPushButton()
        self._quality_next.setObjectName("GlassButton")
        self._quality_next.clicked.connect(lambda: self._show_quality_segment(self._quality_segment_index + 1))
        nav.addStretch(1)
        nav.addWidget(self._quality_prev)
        nav.addWidget(self._quality_next)
        output_layout.addWidget(self._quality_output_title)
        output_layout.addWidget(self._quality_meta)
        output_layout.addWidget(self._quality_image)
        output_layout.addLayout(nav)
        self._quality_output_card.setVisible(False)
        layout.addWidget(self._quality_output_card)
        layout.addStretch(1)
        return page

    def _build_duration_page(self) -> QWidget:
        page = QWidget()
        page.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        page.setAutoFillBackground(False)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        input_card = QFrame()
        input_card.setObjectName("GlassCard")
        input_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        input_layout = QGridLayout(input_card)
        input_layout.setContentsMargins(18, 16, 18, 16)
        input_layout.setHorizontalSpacing(10)
        input_layout.setVerticalSpacing(12)
        self._duration_input_title = QLabel()
        self._duration_input_title.setObjectName("CardTitle")
        self._duration_folder_label = QLabel()
        self._duration_path = QLineEdit(str(PROJECT_ROOT / "inputs"))
        self._duration_choose = QPushButton()
        self._duration_choose.setObjectName("GlassButton")
        self._duration_choose.clicked.connect(lambda: self._choose_folder(self._duration_path))
        self._duration_run = QPushButton()
        self._duration_run.setObjectName("PrimaryButton")
        self._duration_run.clicked.connect(self._start_duration)
        self._duration_drop_area = DropArea(accept_folder=True)
        self._duration_drop_area.path_dropped.connect(self._duration_path.setText)
        input_layout.addWidget(self._duration_input_title, 0, 0, 1, 3)
        input_layout.addWidget(self._duration_folder_label, 1, 0)
        input_layout.addWidget(self._duration_path, 1, 1)
        input_layout.addWidget(self._duration_choose, 1, 2)
        input_layout.addWidget(self._duration_drop_area, 2, 0, 1, 3)
        input_layout.addWidget(self._duration_run, 3, 2)
        input_layout.setColumnStretch(1, 1)
        layout.addWidget(input_card)

        self._duration_output_card = QFrame()
        self._duration_output_card.setObjectName("GlassCard")
        self._duration_output_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        output_layout = QVBoxLayout(self._duration_output_card)
        output_layout.setContentsMargins(18, 16, 18, 16)
        output_layout.setSpacing(12)
        self._duration_output_title = QLabel()
        self._duration_output_title.setObjectName("CardTitle")
        self._duration_text = QLabel()
        self._duration_text.setObjectName("ResultText")
        self._duration_detail = QLabel()
        self._duration_detail.setObjectName("MutedText")
        self._duration_detail.setWordWrap(True)
        output_layout.addWidget(self._duration_output_title)
        output_layout.addWidget(self._duration_text)
        output_layout.addWidget(self._duration_detail)
        self._duration_output_card.setVisible(False)
        layout.addWidget(self._duration_output_card)
        layout.addStretch(1)
        return page

    def _build_pitch_page(self) -> QWidget:
        page = QWidget()
        page.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        page.setAutoFillBackground(False)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        input_card = QFrame()
        input_card.setObjectName("GlassCard")
        input_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        input_layout = QGridLayout(input_card)
        input_layout.setContentsMargins(18, 16, 18, 16)
        input_layout.setHorizontalSpacing(10)
        input_layout.setVerticalSpacing(12)
        self._pitch_input_title = QLabel()
        self._pitch_input_title.setObjectName("CardTitle")
        self._pitch_folder_label = QLabel()
        self._pitch_path = QLineEdit(str(PROJECT_ROOT / "inputs"))
        self._pitch_algorithm_label = QLabel()
        self._pitch_algorithm = QComboBox()
        self._pitch_algorithm.addItem("Praat", "praat")
        self._pitch_algorithm.addItem("RMVPE", "rmvpe")
        self._pitch_choose = QPushButton()
        self._pitch_choose.setObjectName("GlassButton")
        self._pitch_choose.clicked.connect(lambda: self._choose_folder(self._pitch_path))
        self._pitch_run = QPushButton()
        self._pitch_run.setObjectName("PrimaryButton")
        self._pitch_run.clicked.connect(self._start_pitch)
        self._pitch_drop_area = DropArea(accept_folder=True)
        self._pitch_drop_area.path_dropped.connect(self._pitch_path.setText)
        input_layout.addWidget(self._pitch_input_title, 0, 0, 1, 3)
        input_layout.addWidget(self._pitch_folder_label, 1, 0)
        input_layout.addWidget(self._pitch_path, 1, 1)
        input_layout.addWidget(self._pitch_choose, 1, 2)
        input_layout.addWidget(self._pitch_drop_area, 2, 0, 1, 3)
        input_layout.addWidget(self._pitch_algorithm_label, 3, 0)
        input_layout.addWidget(self._pitch_algorithm, 3, 1)
        input_layout.addWidget(self._pitch_run, 3, 2)
        input_layout.setColumnStretch(1, 1)
        layout.addWidget(input_card)

        self._pitch_output_card = QFrame()
        self._pitch_output_card.setObjectName("GlassCard")
        self._pitch_output_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        output_layout = QVBoxLayout(self._pitch_output_card)
        output_layout.setContentsMargins(18, 16, 18, 16)
        output_layout.setSpacing(12)
        self._pitch_output_title = QLabel()
        self._pitch_output_title.setObjectName("CardTitle")
        self._pitch_text = QTextEdit()
        self._pitch_text.setObjectName("ReportText")
        self._pitch_text.setReadOnly(True)
        self._pitch_plot = PreviewImageLabel()
        self._pitch_plot.setObjectName("SpectrogramImage")
        self._pitch_plot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pitch_plot.setMinimumHeight(420)
        self._pitch_plot.preview_requested.connect(self._open_image_preview)
        output_layout.addWidget(self._pitch_output_title)
        output_layout.addWidget(self._pitch_text)
        output_layout.addWidget(self._pitch_plot)
        self._pitch_output_card.setVisible(False)
        layout.addWidget(self._pitch_output_card)
        layout.addStretch(1)
        return page

    def _build_normalize_page(self) -> QWidget:
        page = QWidget()
        page.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        page.setAutoFillBackground(False)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        input_card = QFrame()
        input_card.setObjectName("GlassCard")
        input_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        input_layout = QGridLayout(input_card)
        input_layout.setContentsMargins(18, 16, 18, 16)
        input_layout.setHorizontalSpacing(10)
        input_layout.setVerticalSpacing(12)

        self._normalize_input_title = QLabel()
        self._normalize_input_title.setObjectName("CardTitle")
        self._normalize_input_label = QLabel()
        self._normalize_input_path = QLineEdit(str(PROJECT_ROOT / "inputs"))
        self._normalize_input_choose = QPushButton()
        self._normalize_input_choose.setObjectName("GlassButton")
        self._normalize_input_choose.clicked.connect(lambda: self._choose_folder(self._normalize_input_path))
        self._normalize_input_drop_area = DropArea(accept_folder=True)
        self._normalize_input_drop_area.path_dropped.connect(self._normalize_input_path.setText)

        self._normalize_output_label = QLabel()
        self._normalize_output_path = QLineEdit(str(PROJECT_ROOT / "outputs"))
        self._normalize_output_choose = QPushButton()
        self._normalize_output_choose.setObjectName("GlassButton")
        self._normalize_output_choose.clicked.connect(lambda: self._choose_folder(self._normalize_output_path))
        self._normalize_output_drop_area = DropArea(accept_folder=True)
        self._normalize_output_drop_area.path_dropped.connect(self._normalize_output_path.setText)

        self._normalize_peak_label = QLabel()
        self._normalize_peak = WheelDisabledDoubleSpinBox()
        self._normalize_peak.setRange(-60.0, 0.0)
        self._normalize_peak.setDecimals(1)
        self._normalize_peak.setSingleStep(0.5)
        self._normalize_peak.setValue(-3.0)
        self._normalize_run = QPushButton()
        self._normalize_run.setObjectName("PrimaryButton")
        self._normalize_run.clicked.connect(self._start_normalize)

        input_layout.addWidget(self._normalize_input_title, 0, 0, 1, 3)
        input_layout.addWidget(self._normalize_input_label, 1, 0)
        input_layout.addWidget(self._normalize_input_path, 1, 1)
        input_layout.addWidget(self._normalize_input_choose, 1, 2)
        input_layout.addWidget(self._normalize_input_drop_area, 2, 0, 1, 3)
        input_layout.addWidget(self._normalize_output_label, 3, 0)
        input_layout.addWidget(self._normalize_output_path, 3, 1)
        input_layout.addWidget(self._normalize_output_choose, 3, 2)
        input_layout.addWidget(self._normalize_output_drop_area, 4, 0, 1, 3)
        input_layout.addWidget(self._normalize_peak_label, 5, 0)
        input_layout.addWidget(self._normalize_peak, 5, 1)
        input_layout.addWidget(self._normalize_run, 5, 2)
        input_layout.setColumnStretch(1, 1)
        layout.addWidget(input_card)

        self._normalize_output_card = QFrame()
        self._normalize_output_card.setObjectName("GlassCard")
        self._normalize_output_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        output_layout = QVBoxLayout(self._normalize_output_card)
        output_layout.setContentsMargins(18, 16, 18, 16)
        output_layout.setSpacing(12)
        self._normalize_output_title = QLabel()
        self._normalize_output_title.setObjectName("CardTitle")
        self._normalize_text = QLabel()
        self._normalize_text.setObjectName("MutedText")
        self._normalize_text.setWordWrap(True)
        output_layout.addWidget(self._normalize_output_title)
        output_layout.addWidget(self._normalize_text)
        self._normalize_output_card.setVisible(False)
        layout.addWidget(self._normalize_output_card)
        layout.addStretch(1)
        return page

    @Slot(int)
    def _switch_tool(self, button_id: int) -> None:
        modes = ["quality", "duration", "pitch", "normalize"]
        self._current_mode = modes[button_id]
        self._stack.setCurrentIndex(button_id)

    def _choose_audio_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self._translator.text("settings.choose"),
            str(PROJECT_ROOT / "inputs"),
            "Audio Files (*.wav *.flac *.ogg *.mp3 *.m4a *.aac *.wma);;All Files (*)",
        )
        if file_path:
            self._quality_path.setText(file_path)

    def _choose_folder(self, target: QLineEdit) -> None:
        folder = QFileDialog.getExistingDirectory(self, self._translator.text("settings.choose"), target.text())
        if folder:
            target.setText(folder)

    def _start_quality(self) -> None:
        self._start_worker("quality", Path(self._quality_path.text()))

    def _start_duration(self) -> None:
        self._start_worker("duration", Path(self._duration_path.text()))

    def _start_pitch(self) -> None:
        self._start_worker("pitch", Path(self._pitch_path.text()), pitch_algorithm=str(self._pitch_algorithm.currentData()))

    def _start_normalize(self) -> None:
        self._start_worker(
            "normalize",
            Path(self._normalize_input_path.text()),
            Path(self._normalize_output_path.text()),
            self._normalize_peak.value(),
        )

    def _start_worker(
        self,
        mode: str,
        path: Path,
        output_path: Path | None = None,
        target_peak_db: float = -3.0,
        pitch_algorithm: str = "praat",
    ) -> None:
        if self._thread is not None:
            return
        if not str(path).strip():
            self._set_message(self._translator.text("tools.error.empty_path"))
            return
        if mode == "normalize" and (output_path is None or not str(output_path).strip()):
            self._set_message(self._translator.text("tools.error.empty_path"))
            return
        self._set_buttons_enabled(False)
        self._set_message(self._translator.text(f"tools.{mode}.running"))
        self._thread = QThread(self)
        self._worker = ToolWorker(mode, path, output_path, target_peak_db, pitch_algorithm)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._handle_finished)
        self._worker.failed.connect(self._handle_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)
        self._thread.start()

    @Slot(object)
    def _handle_finished(self, result: object) -> None:
        if isinstance(result, AudioQualityResult):
            self._quality_result = result
            self._quality_segment_index = 0
            self._quality_output_card.setVisible(True)
            self._show_quality_segment(0)
            self._set_message(self._translator.text("tools.quality.done").format(segments=len(result.segments)))
        elif isinstance(result, DurationSummary):
            self._duration_output_card.setVisible(True)
            self._duration_text.setText(result.formatted)
            self._duration_detail.setText(
                self._translator.text("tools.duration.detail").format(
                    files=result.file_count,
                    failed=result.failed_count,
                    directory=result.directory,
                )
            )
            self._set_message(self._translator.text("tools.duration.done").format(result=result.formatted))
        elif isinstance(result, PitchReport):
            self._pitch_output_card.setVisible(True)
            self._pitch_text.setPlainText(result.to_text())
            self._pitch_plot_path = result.plot_path
            if result.plot_path is not None:
                self._set_label_pixmap(self._pitch_plot, result.plot_path)
            else:
                self._pitch_plot.clear()
            self._set_message(self._translator.text("tools.pitch.done").format(frames=result.voiced_frames))
        elif isinstance(result, NormalizeResult):
            self._normalize_output_card.setVisible(True)
            if result.failed_count:
                self._normalize_text.setText(
                    self._translator.text("tools.normalize.done_with_errors").format(
                        success=result.success_count,
                        failed=result.failed_count,
                        files=result.file_count,
                        output=result.output_dir,
                    )
                )
            else:
                self._normalize_text.setText(
                    self._translator.text("tools.normalize.done").format(
                        files=result.success_count,
                        peak=result.target_peak_db,
                        output=result.output_dir,
                    )
                )
            self._set_message(self._normalize_text.text())

    @Slot(str)
    def _handle_failed(self, message: str) -> None:
        self._set_message(self._translator.text("tools.failed").format(error=message))

    @Slot()
    def _cleanup_worker(self) -> None:
        self._set_buttons_enabled(True)
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None

    def _show_quality_segment(self, index: int) -> None:
        if self._quality_result is None or not self._quality_result.segments:
            return
        index = max(0, min(index, len(self._quality_result.segments) - 1))
        self._quality_segment_index = index
        segment = self._quality_result.segments[index]
        self._set_label_pixmap(self._quality_image, segment.image_path)
        self._quality_meta.setText(
            self._translator.text("tools.quality.segment").format(
                current=index + 1,
                total=len(self._quality_result.segments),
                start=self._format_time(segment.start_seconds),
                end=self._format_time(segment.end_seconds),
                rate=self._quality_result.sample_rate,
                channels=self._quality_result.channels,
            )
        )
        self._quality_prev.setEnabled(index > 0)
        self._quality_next.setEnabled(index < len(self._quality_result.segments) - 1)

    def _set_label_pixmap(self, label: QLabel, image_path: Path) -> None:
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            label.clear()
            if isinstance(label, PreviewImageLabel):
                label.set_image_path(None)
            return
        if isinstance(label, PreviewImageLabel):
            label.set_image_path(image_path)
        label.setPixmap(
            pixmap.scaled(
                label.width() or pixmap.width(),
                label.height() or pixmap.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    @Slot(object)
    def _open_image_preview(self, image_path: Path) -> None:
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(str(image_path.name))
        dialog.resize(min(1280, max(900, pixmap.width())), min(860, max(620, pixmap.height())))
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 14, 14, 14)
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        image = QLabel()
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setPixmap(pixmap)
        image.resize(pixmap.size())
        scroll.setWidget(image)
        layout.addWidget(scroll)
        dialog.exec()

    def _refresh_output_images(self) -> None:
        if self._quality_result is not None and self._quality_result.segments:
            self._set_label_pixmap(
                self._quality_image,
                self._quality_result.segments[self._quality_segment_index].image_path,
            )
        if self._pitch_output_card.isVisible() and self._pitch_plot_path is not None:
            self._set_label_pixmap(self._pitch_plot, self._pitch_plot_path)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        for button in (
            self._quality_run,
            self._duration_run,
            self._pitch_run,
            self._normalize_run,
            self._quality_choose,
            self._duration_choose,
            self._pitch_choose,
            self._normalize_input_choose,
            self._normalize_output_choose,
        ):
            button.setEnabled(enabled)

    def _set_message(self, message: str) -> None:
        self.status_changed.emit(message)

    def _format_time(self, seconds: float) -> str:
        seconds = int(round(seconds))
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        remaining = seconds % 60
        if hours:
            return f"{hours}:{minutes:02d}:{remaining:02d}"
        return f"{minutes}:{remaining:02d}"
