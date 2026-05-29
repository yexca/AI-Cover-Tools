from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...slicer import SlicerRunResult, SlicerSettings, run_slicer
from ..i18n import Translator
from ..paths import PROJECT_ROOT
from ..widgets import WheelDisabledDoubleSpinBox, WheelDisabledSpinBox


class SlicerWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, input_dir: Path, output_dir: Path, output_format: str, settings: SlicerSettings) -> None:
        super().__init__()
        self._input_dir = input_dir
        self._output_dir = output_dir
        self._output_format = output_format
        self._settings = settings

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(run_slicer(self._input_dir, self._output_dir, self._output_format, self._settings))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__)


class SlicerPage(QWidget):
    status_changed = Signal(str)

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SlicerPage")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self._translator = translator
        self._thread: QThread | None = None
        self._worker: SlicerWorker | None = None

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
        content.setObjectName("SlicerContent")
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        content.setAutoFillBackground(False)
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(16)

        self._title = QLabel()
        self._title.setObjectName("PageTitle")
        layout.addWidget(self._title)

        self._io_card = QFrame()
        self._io_card.setObjectName("GlassCard")
        io_layout = QGridLayout(self._io_card)
        io_layout.setContentsMargins(18, 16, 18, 16)
        io_layout.setHorizontalSpacing(10)
        io_layout.setVerticalSpacing(12)

        self._io_title = QLabel()
        self._io_title.setObjectName("CardTitle")
        io_layout.addWidget(self._io_title, 0, 0, 1, 3)

        self._input_label = QLabel()
        self._input_path = QLineEdit(str(PROJECT_ROOT / "inputs"))
        self._input_choose = QPushButton()
        self._input_choose.setObjectName("GlassButton")
        self._input_choose.clicked.connect(lambda: self._choose_folder(self._input_path))
        io_layout.addWidget(self._input_label, 1, 0)
        io_layout.addWidget(self._input_path, 1, 1)
        io_layout.addWidget(self._input_choose, 1, 2)

        self._output_label = QLabel()
        self._output_path = QLineEdit(str(PROJECT_ROOT / "outputs"))
        self._output_choose = QPushButton()
        self._output_choose.setObjectName("GlassButton")
        self._output_choose.clicked.connect(lambda: self._choose_folder(self._output_path))
        io_layout.addWidget(self._output_label, 2, 0)
        io_layout.addWidget(self._output_path, 2, 1)
        io_layout.addWidget(self._output_choose, 2, 2)

        self._format_label = QLabel()
        self._format_combo = QComboBox()
        for value in ("wav", "flac", "mp3"):
            self._format_combo.addItem(value, value)
        self._run_button = QPushButton()
        self._run_button.setObjectName("PrimaryButton")
        self._run_button.clicked.connect(self._start_slicing)
        io_layout.addWidget(self._format_label, 3, 0)
        io_layout.addWidget(self._format_combo, 3, 1)
        io_layout.addWidget(self._run_button, 3, 2)
        io_layout.setColumnStretch(1, 1)
        layout.addWidget(self._io_card)

        self._settings_card = QFrame()
        self._settings_card.setObjectName("GlassCard")
        settings_layout = QGridLayout(self._settings_card)
        settings_layout.setContentsMargins(18, 16, 18, 16)
        settings_layout.setHorizontalSpacing(10)
        settings_layout.setVerticalSpacing(12)

        self._settings_title = QLabel()
        self._settings_title.setObjectName("CardTitle")
        settings_layout.addWidget(self._settings_title, 0, 0, 1, 4)

        self._threshold_label = QLabel()
        self._threshold = WheelDisabledDoubleSpinBox()
        self._threshold.setRange(-120.0, 0.0)
        self._threshold.setDecimals(1)
        self._threshold.setSingleStep(1.0)
        self._threshold.setValue(-40.0)

        self._min_length_label = QLabel()
        self._min_length = self._create_ms_spinbox(5000, 1000000)
        self._min_interval_label = QLabel()
        self._min_interval = self._create_ms_spinbox(300, 100000)
        self._hop_size_label = QLabel()
        self._hop_size = self._create_ms_spinbox(10, 1000)
        self._max_silence_label = QLabel()
        self._max_silence = self._create_ms_spinbox(1000, 300000)

        settings_layout.addWidget(self._threshold_label, 1, 0)
        settings_layout.addWidget(self._threshold, 1, 1)
        settings_layout.addWidget(self._min_length_label, 1, 2)
        settings_layout.addWidget(self._min_length, 1, 3)
        settings_layout.addWidget(self._min_interval_label, 2, 0)
        settings_layout.addWidget(self._min_interval, 2, 1)
        settings_layout.addWidget(self._hop_size_label, 2, 2)
        settings_layout.addWidget(self._hop_size, 2, 3)
        settings_layout.addWidget(self._max_silence_label, 3, 0)
        settings_layout.addWidget(self._max_silence, 3, 1)
        settings_layout.setColumnStretch(1, 1)
        settings_layout.setColumnStretch(3, 1)
        layout.addWidget(self._settings_card)

        self._message = QLabel()
        self._message.setObjectName("MutedText")
        self._message.setWordWrap(True)
        layout.addWidget(self._message)
        layout.addStretch(1)

        self.retranslate(translator)

    def retranslate(self, translator: Translator) -> None:
        self._translator = translator
        self._title.setText(translator.text("page.slicer.title"))
        self._io_title.setText(translator.text("slicer.io"))
        self._input_label.setText(translator.text("slicer.input_folder"))
        self._output_label.setText(translator.text("slicer.output_folder"))
        self._format_label.setText(translator.text("slicer.output_format"))
        self._input_choose.setText(translator.text("settings.choose"))
        self._output_choose.setText(translator.text("settings.choose"))
        self._run_button.setText(translator.text("slicer.run"))
        self._settings_title.setText(translator.text("slicer.settings"))
        self._threshold_label.setText(translator.text("slicer.threshold"))
        self._min_length_label.setText(translator.text("slicer.min_length"))
        self._min_interval_label.setText(translator.text("slicer.min_interval"))
        self._hop_size_label.setText(translator.text("slicer.hop_size"))
        self._max_silence_label.setText(translator.text("slicer.max_silence"))

    def _create_ms_spinbox(self, value: int, maximum: int) -> WheelDisabledSpinBox:
        spinbox = WheelDisabledSpinBox()
        spinbox.setRange(1, maximum)
        spinbox.setSingleStep(10)
        spinbox.setValue(value)
        return spinbox

    def _choose_folder(self, target: QLineEdit) -> None:
        folder = QFileDialog.getExistingDirectory(self, self._translator.text("settings.choose"), target.text())
        if folder:
            target.setText(folder)

    def _current_settings(self) -> SlicerSettings | None:
        min_length = self._min_length.value()
        min_interval = self._min_interval.value()
        hop_size = self._hop_size.value()
        max_silence = self._max_silence.value()

        if min_length < min_interval:
            self._set_message(self._translator.text("slicer.error.min_length"))
            return None
        if min_interval < hop_size:
            self._set_message(self._translator.text("slicer.error.min_interval"))
            return None
        if max_silence < hop_size:
            self._set_message(self._translator.text("slicer.error.max_silence"))
            return None

        return SlicerSettings(
            threshold=self._threshold.value(),
            min_length=min_length,
            min_interval=min_interval,
            hop_size=hop_size,
            max_sil_kept=max_silence,
        )

    def _start_slicing(self) -> None:
        settings = self._current_settings()
        if settings is None:
            return

        input_dir = Path(self._input_path.text()).expanduser()
        output_dir = Path(self._output_path.text()).expanduser()
        output_format = str(self._format_combo.currentData())

        self._run_button.setEnabled(False)
        self._set_message(self._translator.text("slicer.running"))
        self._thread = QThread(self)
        self._worker = SlicerWorker(input_dir, output_dir, output_format, settings)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._handle_finished)
        self._worker.failed.connect(self._handle_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)
        self._thread.start()

    @Slot(object)
    def _handle_finished(self, result: SlicerRunResult) -> None:
        if result.source_count == 0:
            message = self._translator.text("slicer.done_empty")
        elif result.failed_count:
            message = self._translator.text("slicer.done_with_errors").format(
                files=result.success_count,
                failed=result.failed_count,
                clips=result.output_count,
                output=result.output_dir,
            )
        else:
            message = self._translator.text("slicer.done").format(
                files=result.success_count,
                clips=result.output_count,
                output=result.output_dir,
            )
        self._set_message(message)

    @Slot(str)
    def _handle_failed(self, message: str) -> None:
        self._set_message(self._translator.text("slicer.failed").format(error=message))

    @Slot()
    def _cleanup_worker(self) -> None:
        self._run_button.setEnabled(True)
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None

    def _set_message(self, message: str) -> None:
        self._message.setText(message)
        self.status_changed.emit(message)
