from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox

from packages.Tabs.GlobalSetting import GlobalSetting


class SubtitleSyncToReferenceCheckBox(QCheckBox):
    def __init__(self, tab_index):
        super().__init__()
        self.tab_index = tab_index
        self.hint_when_enabled = ""
        self.setText("Sync Start Time To Reference")
        self.setToolTip(
            "<nobr>Shift this group's subtitles so every file starts at the same "
            "time as the reference group's file for the SAME row / video.<br>"
            'Select the reference group with "Use as Start-Time Reference".<br>'
            "Requires at least 2 subtitle groups.<br>"
            "The first real dialogue line is used (karaoke/OP lines are skipped).<br>"
            'Use "Review Start Lines" to see the detected line or set a custom start.'
        )
        self.stateChanged.connect(self.change_global_subtitle_sync_to_reference)

    def change_global_subtitle_sync_to_reference(self):
        GlobalSetting.SUBTITLE_SYNC_TO_REFERENCE[self.tab_index] = (
            self.checkState() == Qt.CheckState.Checked
        )

    def update_check_state(self):
        self.setChecked(bool(GlobalSetting.SUBTITLE_SYNC_TO_REFERENCE[self.tab_index]))

    def setEnabled(self, new_state: bool):
        super().setEnabled(new_state)
        if not new_state and not GlobalSetting.JOB_QUEUE_EMPTY:
            if self.hint_when_enabled != "":
                self.setToolTip(
                    "<nobr>"
                    + self.hint_when_enabled
                    + "<br>"
                    + GlobalSetting.DISABLE_TOOLTIP
                )
            else:
                self.setToolTip("<nobr>" + GlobalSetting.DISABLE_TOOLTIP)
        else:
            self.setToolTip(self.hint_when_enabled)

    def setDisabled(self, new_state: bool):
        super().setDisabled(new_state)
        if new_state and not GlobalSetting.JOB_QUEUE_EMPTY:
            if self.hint_when_enabled != "":
                self.setToolTip(
                    "<nobr>"
                    + self.hint_when_enabled
                    + "<br>"
                    + GlobalSetting.DISABLE_TOOLTIP
                )
            else:
                self.setToolTip("<nobr>" + GlobalSetting.DISABLE_TOOLTIP)
        else:
            self.setToolTip(self.hint_when_enabled)

    def setToolTip(self, new_tool_tip: str):
        if self.isEnabled() or GlobalSetting.JOB_QUEUE_EMPTY:
            self.hint_when_enabled = new_tool_tip
        super().setToolTip(new_tool_tip)
