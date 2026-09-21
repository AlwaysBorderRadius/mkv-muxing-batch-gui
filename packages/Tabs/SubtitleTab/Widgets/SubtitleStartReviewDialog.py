from pathlib import Path

from PySide6.QtGui import Qt as QGuiQt
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from packages.Startup.SubtitleStartTimeSync import (
    get_subtitle_cues,
    get_subtitle_dialogue_start_cue,
)
from packages.Tabs.GlobalSetting import GlobalSetting
from packages.Widgets.MyDialog import MyDialog

DROPDOWN_MAX_LINES = 100


def _seconds_to_hms(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    hours, remainder = divmod(total_ms, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    secs = remainder / 1000.0
    if hours:
        return f"{hours}:{minutes:02d}:{secs:06.3f}"
    return f"{minutes}:{secs:06.3f}"


def _clean_warning_line(text: str) -> str:
    if len(text) > 45:
        return text[:45] + "..."
    return text


class SubtitleStartReviewDialog(MyDialog):
    def __init__(self, tab_index, parent=None):
        super().__init__(parent)
        self.window_title = "Start-Time Review"
        self.state = "no"
        self.tab_index = tab_index
        self.files_list = GlobalSetting.SUBTITLE_FILES_LIST[tab_index]
        self.files_absolute_list = GlobalSetting.SUBTITLE_FILES_ABSOLUTE_PATH_LIST[
            tab_index
        ]
        self.current_file_absolute_path = ""
        self.current_detected_ms = None
        self.reference_tab_index = None
        self.reference_absolute_path = ""
        self.reference_detected_ms = None

        self.subtitle_file_combo = QComboBox()
        self.subtitle_file_combo.addItems(self.files_list)
        self.subtitle_file_combo.currentIndexChanged.connect(self.update_current_file)

        self.detected_time_label = QLabel("")
        self.detected_time_label.setStyleSheet("font-weight: bold;")

        self.line_combo = QComboBox()
        self.line_combo.setToolTip(
            "<nobr>Pick the subtitle line to use as start-time for this file.<br>"
            "The detected line is selected by default; picking it again reverts "
            "to the detected start-time.<br>"
            "Selecting another line overrides the start-time with that line."
        )
        self.line_combo.currentIndexChanged.connect(self.save_current_override)

        self.this_group_box = QGroupBox("This Subtitle")
        this_layout = QVBoxLayout()
        this_layout.addWidget(self.line_combo)
        self.this_group_box.setLayout(this_layout)

        self.reference_group_box = QGroupBox("Reference Subtitle")
        self.reference_group_box.setMinimumWidth(280)
        self.reference_file_label = QLabel("")
        self.reference_file_label.setWordWrap(True)
        self.reference_time_label = QLabel("")
        self.reference_time_label.setWordWrap(True)
        self.reference_line_combo = QComboBox()
        self.reference_line_combo.setToolTip(
            "<nobr>Line used as start-time reference for the matching file.<br>"
            "Picking another line overrides the reference start-time for that file."
        )
        self.reference_line_combo.currentIndexChanged.connect(
            self.save_reference_override
        )
        self.reference_line_combo.setEnabled(False)
        reference_layout = QVBoxLayout()
        reference_layout.addWidget(self.reference_file_label)
        reference_layout.addWidget(self.reference_time_label)
        reference_layout.addWidget(self.reference_line_combo)
        self.reference_group_box.setLayout(reference_layout)

        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")

        self.columns_layout = QHBoxLayout()
        self.columns_layout.addWidget(self.this_group_box, 1)
        self.columns_layout.addWidget(self.reference_group_box, 1)

        self.form_layout = QGridLayout()
        self.form_layout.addWidget(QLabel("Subtitle File:"), 0, 0)
        self.form_layout.addWidget(self.subtitle_file_combo, 0, 1, 1, 2)
        self.form_layout.addWidget(self.detected_time_label, 1, 0, 1, 3)
        self.form_layout.addLayout(self.columns_layout, 2, 0, 1, 3)

        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.addStretch()
        self.buttons_layout.addWidget(self.ok_button)
        self.buttons_layout.addWidget(self.cancel_button)
        self.buttons_layout.addStretch()

        main_layout = QVBoxLayout()
        main_layout.addLayout(self.form_layout)
        main_layout.addLayout(self.buttons_layout)
        main_layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(main_layout)

        self.setWindowTitle(self.window_title)
        self.setModal(True)
        self.ok_button.clicked.connect(self.click_ok)
        self.cancel_button.clicked.connect(self.click_no)

        self.subtitle_file_combo.setCurrentIndex(0)
        self.update_current_file()

    def get_selected_file_index(self):
        current_index = self.subtitle_file_combo.currentIndex()
        if 0 <= current_index < len(self.files_absolute_list):
            return current_index
        return -1

    def get_reference_tab_index(self):
        reference_tab_index = None
        for i in GlobalSetting.SUBTITLE_SET_AS_REFERENCE:
            if GlobalSetting.SUBTITLE_SET_AS_REFERENCE[i] and i != self.tab_index:
                reference_tab_index = i
                break
        if (
            reference_tab_index is None
            and GlobalSetting.SUBTITLE_SET_AS_REFERENCE[self.tab_index]
        ):
            return self.tab_index
        return reference_tab_index

    def update_current_file(self):
        self.save_current_override()
        self.save_reference_override()
        index = self.get_selected_file_index()
        if index == -1:
            self.current_file_absolute_path = ""
            self.current_detected_ms = None
            self.detected_time_label.setText("")
            self._disable_line_combo()
            self.update_reference_column(index)
            return
        self.current_file_absolute_path = self.files_absolute_list[index]
        override_map = GlobalSetting.SUBTITLE_SYNC_START_OVERRIDES.get(self.tab_index, {})
        override_start_ms = override_map.get(self.current_file_absolute_path)
        cue, is_fallback = get_subtitle_dialogue_start_cue(
            self.current_file_absolute_path
        )
        if cue is None:
            self.current_detected_ms = None
            self.detected_time_label.setText("Not supported or unreadable")
            self._disable_line_combo()
            self.update_reference_column(index)
            return
        detected_seconds = cue.start_ms / 1000.0
        detected_text = "Detected Start-Time: " + _seconds_to_hms(detected_seconds)
        detected_text += " (" + str(round(detected_seconds, 3)) + " s)"
        if is_fallback:
            detected_text += "  [looks like karaoke/sign lines]"
        self.detected_time_label.setText(detected_text)
        self.current_detected_ms = cue.start_ms
        self._populate_start_line_combo(
            self.line_combo, self.current_file_absolute_path, cue, override_start_ms
        )
        self.update_reference_column(index)

    def _disable_line_combo(self):
        self.line_combo.blockSignals(True)
        self.line_combo.clear()
        self.line_combo.blockSignals(False)
        self.line_combo.setEnabled(False)

    def _disable_reference_combo(self):
        self.reference_line_combo.blockSignals(True)
        self.reference_line_combo.clear()
        self.reference_line_combo.blockSignals(False)
        self.reference_line_combo.setEnabled(False)

    def _populate_start_line_combo(
        self, combo, absolute_path, detected_cue, override_ms=None
    ):
        combo.blockSignals(True)
        combo.clear()
        try:
            all_cues = get_subtitle_cues(absolute_path)
        except OSError:
            all_cues = []
        candidates = [candidate for candidate in all_cues if candidate.text.strip()]
        target_ms = override_ms if override_ms is not None else detected_cue.start_ms
        target_slot = -1
        for i, candidate in enumerate(candidates):
            if candidate.start_ms == target_ms:
                target_slot = i
                break
        selected_index = 0
        chunk = candidates[:DROPDOWN_MAX_LINES]
        for i, candidate in enumerate(chunk):
            label = _seconds_to_hms(candidate.start_ms / 1000.0)
            label += " — " + _clean_warning_line(candidate.text)
            combo.addItem(label)
            combo.setItemData(combo.count() - 1, candidate.start_ms)
            if i == target_slot:
                selected_index = combo.count() - 1
        if target_slot == -1 and override_ms is not None:
            custom_label = _seconds_to_hms(override_ms / 1000.0) + " (custom)"
            combo.addItem(custom_label)
            combo.setItemData(combo.count() - 1, override_ms)
            selected_index = combo.count() - 1
        elif target_slot >= DROPDOWN_MAX_LINES:
            candidate = candidates[target_slot]
            label = _seconds_to_hms(candidate.start_ms / 1000.0)
            label += " — " + _clean_warning_line(candidate.text)
            combo.addItem(label)
            combo.setItemData(combo.count() - 1, candidate.start_ms)
            selected_index = combo.count() - 1
        elif target_slot == -1 and combo.count() == 0:
            fallback_label = "Auto (detected: " + _seconds_to_hms(
                detected_cue.start_ms / 1000.0
            )
            fallback_label += ")"
            combo.addItem(fallback_label)
            combo.setItemData(0, None)
        combo.setEnabled(True)
        if combo.count() > 0:
            combo.setCurrentIndex(selected_index)
        combo.blockSignals(False)

    def update_reference_column(self, index):
        reference_tab_index = self.get_reference_tab_index()
        self.reference_tab_index = reference_tab_index
        self.reference_absolute_path = ""
        self.reference_detected_ms = None
        if reference_tab_index is None:
            self.reference_file_label.setText("No reference group selected")
            self.reference_time_label.setText("")
            self._disable_reference_combo()
            return
        if reference_tab_index == self.tab_index:
            self.reference_file_label.setText("This group is the Start-Time Reference")
            self.reference_time_label.setText("")
            self._disable_reference_combo()
            return
        reference_absolute_list = GlobalSetting.SUBTITLE_FILES_ABSOLUTE_PATH_LIST.get(
            reference_tab_index, []
        )
        if index < 0 or index >= len(reference_absolute_list):
            self.reference_file_label.setText("No matching file in reference group")
            self.reference_time_label.setText("")
            self._disable_reference_combo()
            return
        reference_absolute_path = reference_absolute_list[index]
        self.reference_absolute_path = reference_absolute_path
        reference_name = Path(reference_absolute_path).name
        if len(reference_name) > 45:
            reference_name = reference_name[:45] + "..."
        self.reference_file_label.setText(reference_name)
        reference_override_map = GlobalSetting.SUBTITLE_SYNC_START_OVERRIDES.get(
            reference_tab_index, {}
        )
        reference_override_ms = reference_override_map.get(reference_absolute_path)
        reference_cue, reference_is_fallback = get_subtitle_dialogue_start_cue(
            reference_absolute_path
        )
        if reference_cue is None:
            self.reference_detected_ms = None
            self.reference_time_label.setText("Not supported or unreadable")
            self._disable_reference_combo()
            return
        self.reference_detected_ms = reference_cue.start_ms
        reference_start_ms = (
            reference_override_ms
            if reference_override_ms is not None
            else reference_cue.start_ms
        )
        reference_time_text = (
            "Start-Time: "
            + _seconds_to_hms(reference_start_ms / 1000.0)
            + " ("
            + str(round(reference_start_ms / 1000.0, 3))
            + " s)"
        )
        if reference_is_fallback:
            reference_time_text += "  [looks like karaoke/sign lines]"
        if reference_override_ms is not None:
            reference_time_text += "  [custom override]"
        self.reference_time_label.setText(reference_time_text)
        self._populate_start_line_combo(
            self.reference_line_combo,
            reference_absolute_path,
            reference_cue,
            reference_override_ms,
        )

    def click_ok(self):
        self.save_current_override()
        self.save_reference_override()
        self.state = "yes"
        self.close()

    def click_no(self):
        self.state = "no"
        self.close()

    def save_current_override(self):
        if self.current_file_absolute_path == "":
            return
        current_data = self.line_combo.currentData()
        override_map = GlobalSetting.SUBTITLE_SYNC_START_OVERRIDES.setdefault(
            self.tab_index, {}
        )
        if current_data is None or current_data == self.current_detected_ms:
            override_map.pop(self.current_file_absolute_path, None)
        else:
            override_map[self.current_file_absolute_path] = int(current_data)

    def save_reference_override(self):
        if self.reference_absolute_path == "":
            return
        if self.reference_tab_index is None:
            return
        current_data = self.reference_line_combo.currentData()
        override_map = GlobalSetting.SUBTITLE_SYNC_START_OVERRIDES.setdefault(
            self.reference_tab_index, {}
        )
        if current_data is None or current_data == self.reference_detected_ms:
            override_map.pop(self.reference_absolute_path, None)
        else:
            override_map[self.reference_absolute_path] = int(current_data)

    def closeEvent(self, event):
        if self.state == "no":
            self.save_current_override()
            self.save_reference_override()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == QGuiQt.Key.Key_Escape:
            self.click_no()
            return
        super().keyPressEvent(event)

    def execute(self):
        self.exec()
