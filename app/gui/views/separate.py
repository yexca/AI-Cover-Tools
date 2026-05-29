from __future__ import annotations

import pprint
import sys
from typing import Any

from PySide6.QtCore import QProcess, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QCheckBox,
    QVBoxLayout,
    QWidget,
)

from ..i18n import Translator
from ..paths import PROJECT_ROOT
from ..storage import MODEL_CATEGORIES, SeparateStore
from ..widgets import WheelDisabledSpinBox


GUI_RUN_CONFIG_PATH = PROJECT_ROOT / "user_data" / "gui_separate_config.py"


class ModelCard(QFrame):
    move_up = Signal(object)
    move_down = Signal(object)
    remove_requested = Signal(object)

    def __init__(
        self,
        module: dict[str, Any],
        translator: Translator,
        index: int,
        model_library: dict[str, dict[str, Any]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("GlassCard")
        self._translator = translator
        self._category = str(module.get("category", "instrumental"))
        self._model_library = dict(model_library or {})
        model = dict(module.get("model", {}))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        self._title = QLabel()
        self._title.setObjectName("CardTitle")
        header.addWidget(self._title, 1)

        self._up_button = QPushButton("↑")
        self._up_button.setObjectName("IconTextButton")
        self._up_button.clicked.connect(lambda: self.move_up.emit(self))
        self._down_button = QPushButton("↓")
        self._down_button.setObjectName("IconTextButton")
        self._down_button.clicked.connect(lambda: self.move_down.emit(self))
        self._remove_button = QPushButton()
        self._remove_button.setObjectName("GlassButton")
        self._remove_button.clicked.connect(lambda: self.remove_requested.emit(self))
        header.addWidget(self._up_button)
        header.addWidget(self._down_button)
        header.addWidget(self._remove_button)
        layout.addLayout(header)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addLayout(form)

        self._label_input = QLineEdit(str(model.get("label", "")))
        self._filename_input = QComboBox()
        self._filename_input.setEditable(True)
        self._filename_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._filename_input.setMinimumWidth(260)
        self._refresh_model_combo(str(model.get("model_filename", "")))
        self._filename_input.activated[int].connect(self._apply_saved_model)
        self._keep_stem_input = QLineEdit(str(model.get("keep_stem", "")))
        self._aliases_input = QLineEdit(", ".join(model.get("stem_aliases", [])))
        self._pitch_shift_input = WheelDisabledSpinBox()
        self._pitch_shift_input.setRange(-24, 24)
        self._pitch_shift_input.setValue(int(model.get("pitch_shift", 0)))

        self._label_label = QLabel()
        self._filename_label = QLabel()
        self._keep_stem_label = QLabel()
        self._aliases_label = QLabel()
        self._pitch_shift_label = QLabel()
        form.addRow(self._label_label, self._label_input)
        form.addRow(self._filename_label, self._filename_input)
        form.addRow(self._keep_stem_label, self._keep_stem_input)
        form.addRow(self._aliases_label, self._aliases_input)
        form.addRow(self._pitch_shift_label, self._pitch_shift_input)

        self.set_index(index)
        self.retranslate(translator)

    def set_index(self, index: int) -> None:
        self._index = index
        self._refresh_title()

    def set_move_enabled(self, can_move_up: bool, can_move_down: bool) -> None:
        self._up_button.setEnabled(can_move_up)
        self._down_button.setEnabled(can_move_down)

    @property
    def category(self) -> str:
        return self._category

    def set_model_library(self, model_library: dict[str, dict[str, Any]]) -> None:
        self._model_library = dict(model_library)
        self._refresh_model_combo(self._model_filename())

    def payload(self) -> dict[str, Any]:
        aliases = [item.strip() for item in self._aliases_input.text().split(",") if item.strip()]
        return {
            "category": self._category,
            "model": {
                "label": self._label_input.text().strip(),
                "model_filename": self._model_filename(),
                "keep_stem": self._keep_stem_input.text().strip(),
                "stem_aliases": aliases,
                "pitch_shift": self._pitch_shift_input.value(),
            },
        }

    def retranslate(self, translator: Translator) -> None:
        self._translator = translator
        self._label_label.setText(translator.text("separate.card.label"))
        self._filename_label.setText(translator.text("separate.card.model_filename"))
        self._keep_stem_label.setText(translator.text("separate.card.keep_stem"))
        self._aliases_label.setText(translator.text("separate.card.stem_aliases"))
        self._pitch_shift_label.setText(translator.text("separate.card.pitch_shift"))
        self._remove_button.setText(translator.text("separate.remove"))
        self._refresh_model_combo(self._model_filename())
        self._refresh_title()

    def _refresh_model_combo(self, current_text: str) -> None:
        self._filename_input.blockSignals(True)
        self._filename_input.clear()

        model_names = sorted(self._model_library.keys())
        if model_names:
            self._filename_input.addItems(model_names)
            completer = QCompleter(model_names, self._filename_input)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self._filename_input.setCompleter(completer)
            self._filename_input.lineEdit().setPlaceholderText(self._translator.text("separate.card.model_filename"))
        else:
            self._filename_input.addItem(self._translator.text("separate.no_saved_models"), "")
            self._filename_input.setCompleter(None)
            self._filename_input.lineEdit().setPlaceholderText(self._translator.text("separate.no_saved_models"))

        if current_text:
            index = self._filename_input.findText(current_text)
            if index >= 0 and model_names:
                self._filename_input.setCurrentIndex(index)
            else:
                self._filename_input.setCurrentIndex(-1)
                self._filename_input.setEditText(current_text)
        else:
            self._filename_input.setCurrentIndex(-1)
            self._filename_input.setEditText("")

        self._filename_input.blockSignals(False)

    def _apply_saved_model(self, index: int) -> None:
        model_filename = str(self._filename_input.itemData(index) or self._filename_input.itemText(index)).strip()
        model = self._model_library.get(model_filename)
        if not model:
            self._filename_input.setCurrentIndex(-1)
            self._filename_input.setEditText("")
            return

        self._filename_input.setEditText(str(model.get("model_filename", model_filename)))
        self._label_input.setText(str(model.get("label", "")))
        self._keep_stem_input.setText(str(model.get("keep_stem", "")))
        self._aliases_input.setText(", ".join(model.get("stem_aliases", [])))
        self._pitch_shift_input.setValue(int(model.get("pitch_shift", 0)))

    def _model_filename(self) -> str:
        text = self._filename_input.currentText().strip()
        if text == self._translator.text("separate.no_saved_models") and not self._model_library:
            return ""
        return text

    def _refresh_title(self) -> None:
        category = self._translator.text(f"separate.category.{self._category}")
        self._title.setText(f"{self._index + 1}. {category}")


class SeparatePage(QWidget):
    status_changed = Signal(str)

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SeparatePage")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self._translator = translator
        self._store = SeparateStore()
        self._cards: list[ModelCard] = []
        self._process: QProcess | None = None
        self._last_process_line = ""
        self._stop_requested = False

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
        content.setObjectName("SeparateContent")
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        content.setAutoFillBackground(False)
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(16)

        self._title = QLabel()
        self._title.setObjectName("PageTitle")
        layout.addWidget(self._title)

        self._preset_card = QFrame()
        self._preset_card.setObjectName("GlassCard")
        preset_layout = QGridLayout(self._preset_card)
        preset_layout.setContentsMargins(18, 16, 18, 16)
        preset_layout.setSpacing(10)
        self._preset_title = QLabel()
        self._preset_title.setObjectName("CardTitle")
        self._preset_combo = QComboBox()
        self._preset_combo.setEditable(True)
        self._preset_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._preset_combo.setMinimumWidth(260)
        self._load_button = QPushButton()
        self._load_button.setObjectName("GlassButton")
        self._save_button = QPushButton()
        self._save_button.setObjectName("GlassButton")
        self._delete_button = QPushButton()
        self._delete_button.setObjectName("GlassButton")
        self._add_category = QComboBox()
        for category in MODEL_CATEGORIES:
            self._add_category.addItem("", category)
        self._add_button = QPushButton()
        self._add_button.setObjectName("GlassButton")
        self._run_button = QPushButton()
        self._run_button.setObjectName("PrimaryButton")
        self._stop_button = QPushButton()
        self._stop_button.setObjectName("DangerButton")
        preset_layout.addWidget(self._preset_title, 0, 0, 1, 5)
        preset_layout.addWidget(self._preset_combo, 1, 0, 1, 2)
        preset_layout.addWidget(self._load_button, 1, 2)
        preset_layout.addWidget(self._save_button, 1, 3)
        preset_layout.addWidget(self._delete_button, 1, 4)
        preset_layout.addWidget(self._add_category, 2, 0, 1, 2)
        preset_layout.addWidget(self._add_button, 2, 2)
        preset_layout.addWidget(self._run_button, 2, 3)
        preset_layout.addWidget(self._stop_button, 2, 4)
        preset_layout.setColumnStretch(0, 1)
        preset_layout.setColumnStretch(1, 1)
        layout.addWidget(self._preset_card)

        self._common_card = QFrame()
        self._common_card.setObjectName("GlassCard")
        common_layout = QGridLayout(self._common_card)
        common_layout.setContentsMargins(18, 16, 18, 16)
        common_layout.setSpacing(10)
        self._common_title = QLabel()
        self._common_title.setObjectName("CardTitle")
        common_layout.addWidget(self._common_title, 0, 0, 1, 4)
        self._batch_size = WheelDisabledSpinBox()
        self._batch_size.setRange(1, 256)
        self._batch_size.setValue(16)
        self._overlap = WheelDisabledSpinBox()
        self._overlap.setRange(0, 32)
        self._overlap.setValue(2)
        self._segment_size = WheelDisabledSpinBox()
        self._segment_size.setRange(32, 4096)
        self._segment_size.setValue(256)
        self._override_segment = QCheckBox()
        self._batch_label = QLabel()
        self._overlap_label = QLabel()
        self._segment_label = QLabel()
        self._override_label = QLabel()
        common_layout.addWidget(self._batch_label, 1, 0)
        common_layout.addWidget(self._batch_size, 1, 1)
        common_layout.addWidget(self._overlap_label, 1, 2)
        common_layout.addWidget(self._overlap, 1, 3)
        common_layout.addWidget(self._segment_label, 2, 0)
        common_layout.addWidget(self._segment_size, 2, 1)
        common_layout.addWidget(self._override_label, 2, 2)
        common_layout.addWidget(self._override_segment, 2, 3)
        common_layout.setColumnStretch(1, 1)
        common_layout.setColumnStretch(3, 1)
        layout.addWidget(self._common_card)

        self._message = QLabel()
        self._message.setObjectName("MutedText")
        self._message.setWordWrap(True)
        layout.addWidget(self._message)

        self._modules_title = QLabel()
        self._modules_title.setObjectName("SectionTitle")
        layout.addWidget(self._modules_title)
        self._cards_layout = QVBoxLayout()
        self._cards_layout.setSpacing(12)
        layout.addLayout(self._cards_layout)
        layout.addStretch(1)

        self._load_button.clicked.connect(self._load_selected_preset)
        self._save_button.clicked.connect(self._save_preset)
        self._delete_button.clicked.connect(self._delete_preset)
        self._add_button.clicked.connect(self._add_selected_category)
        self._run_button.clicked.connect(self._start_separation)
        self._stop_button.clicked.connect(self._stop_separation)
        self._stop_button.setEnabled(False)

        self._refresh_presets()
        self._add_module(self._store.default_module("instrumental"))
        self.retranslate(translator)

    def retranslate(self, translator: Translator) -> None:
        self._translator = translator
        self._title.setText(translator.text("page.separate.title"))
        self._preset_title.setText(translator.text("separate.presets"))
        self._preset_combo.lineEdit().setPlaceholderText(translator.text("separate.preset_name"))
        self._load_button.setText(translator.text("separate.load"))
        self._save_button.setText(translator.text("separate.save"))
        self._delete_button.setText(translator.text("separate.delete"))
        self._add_button.setText(translator.text("separate.add_module"))
        self._run_button.setText(translator.text("separate.run"))
        self._stop_button.setText(translator.text("separate.stop"))
        self._common_title.setText(translator.text("separate.common_settings"))
        self._batch_label.setText("MODEL_BATCH_SIZE")
        self._overlap_label.setText("MODEL_OVERLAP")
        self._segment_label.setText("MODEL_SEGMENT_SIZE")
        self._override_label.setText("MODEL_OVERRIDE_SEGMENT_SIZE")
        self._modules_title.setText(translator.text("separate.modules"))
        for index in range(self._add_category.count()):
            category = str(self._add_category.itemData(index))
            self._add_category.setItemText(index, translator.text(f"separate.category.{category}"))
        for card in self._cards:
            card.retranslate(translator)
        self._refresh_presets()
        self._refresh_model_libraries()

    def current_payload(self) -> dict[str, Any]:
        return {
            "common": {
                "MODEL_BATCH_SIZE": self._batch_size.value(),
                "MODEL_OVERLAP": self._overlap.value(),
                "MODEL_SEGMENT_SIZE": self._segment_size.value(),
                "MODEL_OVERRIDE_SEGMENT_SIZE": self._override_segment.isChecked(),
            },
            "modules": [card.payload() for card in self._cards],
        }

    def _refresh_presets(self) -> None:
        current = self._preset_combo.currentText()
        presets = sorted(self._store.load_presets().keys())
        self._preset_combo.clear()
        if presets:
            self._preset_combo.addItems(presets)
            completer = QCompleter(presets, self._preset_combo)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self._preset_combo.setCompleter(completer)
        else:
            self._preset_combo.addItem(self._translator.text("separate.no_presets"))
            self._preset_combo.setCurrentIndex(0)
            self._preset_combo.setCompleter(None)
        if current and presets:
            index = self._preset_combo.findText(current)
            if index >= 0:
                self._preset_combo.setCurrentIndex(index)

    def _add_selected_category(self) -> None:
        self._add_module(self._store.default_module(str(self._add_category.currentData())))

    def _add_module(self, module: dict[str, Any]) -> None:
        category = str(module.get("category", "instrumental"))
        model_library = self._store.load_model_library().get(category, {})
        card = ModelCard(module, self._translator, len(self._cards), model_library)
        card.move_up.connect(self._move_card_up)
        card.move_down.connect(self._move_card_down)
        card.remove_requested.connect(self._remove_card)
        self._cards.append(card)
        self._cards_layout.addWidget(card)
        self._sync_card_order()

    def _remove_card(self, card: ModelCard) -> None:
        if card not in self._cards:
            return
        self._cards.remove(card)
        card.setParent(None)
        card.deleteLater()
        self._sync_card_order()

    def _move_card_up(self, card: ModelCard) -> None:
        index = self._cards.index(card)
        if index <= 0:
            return
        self._cards[index - 1], self._cards[index] = self._cards[index], self._cards[index - 1]
        self._sync_card_order()

    def _move_card_down(self, card: ModelCard) -> None:
        index = self._cards.index(card)
        if index >= len(self._cards) - 1:
            return
        self._cards[index + 1], self._cards[index] = self._cards[index], self._cards[index + 1]
        self._sync_card_order()

    def _sync_card_order(self) -> None:
        for index, card in enumerate(self._cards):
            self._cards_layout.removeWidget(card)
            self._cards_layout.insertWidget(index, card)
            card.set_index(index)
            card.set_move_enabled(index > 0, index < len(self._cards) - 1)

    def _save_preset(self) -> None:
        name = self._preset_combo.currentText().strip()
        if name == self._translator.text("separate.no_presets"):
            name = ""
        if not name:
            return
        self._store.save_preset(name, self.current_payload())
        self._refresh_presets()
        index = self._preset_combo.findText(name)
        if index >= 0:
            self._preset_combo.setCurrentIndex(index)

    def _delete_preset(self) -> None:
        name = self._preset_combo.currentText().strip()
        if name == self._translator.text("separate.no_presets"):
            return
        if not name:
            return
        self._store.delete_preset(name)
        self._refresh_presets()

    def _load_selected_preset(self) -> None:
        name = self._preset_combo.currentText().strip()
        if name == self._translator.text("separate.no_presets"):
            return
        presets = self._store.load_presets()
        payload = presets.get(name)
        if not payload:
            return
        common = payload.get("common", {})
        self._batch_size.setValue(int(common.get("MODEL_BATCH_SIZE", 16)))
        self._overlap.setValue(int(common.get("MODEL_OVERLAP", 2)))
        self._segment_size.setValue(int(common.get("MODEL_SEGMENT_SIZE", 256)))
        self._override_segment.setChecked(bool(common.get("MODEL_OVERRIDE_SEGMENT_SIZE", False)))
        for card in list(self._cards):
            self._remove_card(card)
        for module in payload.get("modules", []):
            self._add_module(module)

    def _start_separation(self) -> None:
        payload = self.current_payload()
        error = self._validate_payload(payload)
        if error:
            self._set_message(error)
            return

        self._write_run_config(payload)
        self._run_button.setEnabled(False)
        self._stop_button.setEnabled(True)
        self._last_process_line = ""
        self._stop_requested = False
        self._set_message(self._translator.text("separate.running"))

        process = QProcess(self)
        process.setWorkingDirectory(str(PROJECT_ROOT))
        process.setProgram(sys.executable)
        process.setArguments(["main.py", "--config", str(GUI_RUN_CONFIG_PATH)])
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self._handle_process_output)
        process.errorOccurred.connect(self._handle_process_error)
        process.finished.connect(self._handle_process_finished)
        self._process = process
        process.start()

        if not process.waitForStarted(3000):
            self._set_message(self._translator.text("separate.failed").format(error=process.errorString()))
            self._cleanup_process()

    def _stop_separation(self) -> None:
        if self._process is None:
            self._cleanup_process()
            return
        self._set_message(self._translator.text("separate.stopping"))
        self._stop_requested = True
        self._process.terminate()
        if not self._process.waitForFinished(3000):
            self._process.kill()

    def _validate_payload(self, payload: dict[str, Any]) -> str | None:
        modules = payload.get("modules", [])
        if not modules:
            return self._translator.text("separate.error.no_modules")
        for index, module in enumerate(modules, start=1):
            model = dict(module.get("model", {}))
            if not str(model.get("label", "")).strip():
                return self._translator.text("separate.error.missing_label").format(index=index)
            if not str(model.get("model_filename", "")).strip():
                return self._translator.text("separate.error.missing_model").format(index=index)
            if not str(model.get("keep_stem", "")).strip():
                return self._translator.text("separate.error.missing_stem").format(index=index)
        return None

    def _write_run_config(self, payload: dict[str, Any]) -> None:
        GUI_RUN_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        common = dict(payload["common"])
        pipeline = []
        for module in payload["modules"]:
            model = dict(module["model"])
            pipeline.append(
                {
                    "label": model["label"],
                    "model_filename": model["model_filename"],
                    "keep_stem": model["keep_stem"],
                    "stem_aliases": model.get("stem_aliases", []),
                    "pitch_shift": model.get("pitch_shift", 0),
                }
            )

        config_text = (
            "from __future__ import annotations\n\n"
            "import importlib.util\n"
            "from pathlib import Path\n\n"
            f"_BASE_CONFIG = Path({str(PROJECT_ROOT / 'config.py')!r})\n"
            "_spec = importlib.util.spec_from_file_location('ai_cover_gui_base_config', _BASE_CONFIG)\n"
            "if _spec is not None and _spec.loader is not None:\n"
            "    _base_config = importlib.util.module_from_spec(_spec)\n"
            "    _spec.loader.exec_module(_base_config)\n"
            "    for _name in dir(_base_config):\n"
            "        if _name.isupper():\n"
            "            globals()[_name] = getattr(_base_config, _name)\n\n"
            f"MODEL_BATCH_SIZE = {common['MODEL_BATCH_SIZE']!r}\n"
            f"MODEL_OVERLAP = {common['MODEL_OVERLAP']!r}\n"
            f"MODEL_SEGMENT_SIZE = {common['MODEL_SEGMENT_SIZE']!r}\n"
            f"MODEL_OVERRIDE_SEGMENT_SIZE = {common['MODEL_OVERRIDE_SEGMENT_SIZE']!r}\n\n"
            f"MODEL_PIPELINE = {pprint.pformat(pipeline, width=120)}\n"
        )
        GUI_RUN_CONFIG_PATH.write_text(config_text, encoding="utf-8")

    def _handle_process_output(self) -> None:
        if self._process is None:
            return
        text = bytes(self._process.readAllStandardOutput()).decode(errors="replace").strip()
        if not text:
            return
        last_line = text.splitlines()[-1].strip()
        if last_line:
            self._last_process_line = last_line
            self._set_message(last_line)

    def _handle_process_error(self, _error: QProcess.ProcessError) -> None:
        if self._process is None:
            return
        self._set_message(self._translator.text("separate.failed").format(error=self._process.errorString()))

    def _handle_process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        if self._stop_requested:
            self._set_message(self._translator.text("separate.stopped"))
        elif exit_status == QProcess.ExitStatus.CrashExit:
            self._set_message(self._translator.text("separate.stopped"))
        elif exit_code == 0:
            self._store.save_successful_models(self.current_payload()["modules"])
            self._refresh_model_libraries()
            self._set_message(self._last_process_line or self._translator.text("separate.done"))
        else:
            error = self._last_process_line or f"exit code {exit_code}"
            self._set_message(self._translator.text("separate.failed").format(error=error))
        self._cleanup_process()

    def _cleanup_process(self) -> None:
        self._run_button.setEnabled(True)
        self._stop_button.setEnabled(False)
        self._stop_requested = False
        if self._process is not None:
            self._process.deleteLater()
            self._process = None

    def _set_message(self, message: str) -> None:
        self._message.setText(message)
        self.status_changed.emit(message)

    def _refresh_model_libraries(self) -> None:
        library = self._store.load_model_library()
        for card in self._cards:
            card.set_model_library(library.get(card.category, {}))
