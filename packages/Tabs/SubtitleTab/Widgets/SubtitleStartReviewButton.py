from PySide6.QtWidgets import QPushButton

from packages.Tabs.GlobalSetting import GlobalSetting
from packages.Tabs.SubtitleTab.Widgets.SubtitleStartReviewDialog import (
    SubtitleStartReviewDialog,
)


class SubtitleStartReviewButton(QPushButton):
    def __init__(self, tab_index):
        super().__init__()
        self.tab_index = tab_index
        self.hint_when_enabled = ""
        self.setText("Review Start Lines")
        self.setToolTip(
            "<nobr>Show the subtitle line that is used as the detected first "
            "dialogue line and optionally override the start-time used for the "
            "Start-Time Sync feature.<br>Each subtitle file of this group is "
            "reviewed separately."
        )
        self.clicked.connect(self.open_review_dialog)

    def open_review_dialog(self):
        dialog = SubtitleStartReviewDialog(tab_index=self.tab_index, parent=self.window())
        dialog.execute()

    def update_check_state(self):
        self.setEnabled(len(GlobalSetting.SUBTITLE_FILES_LIST[self.tab_index]) > 0)

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
