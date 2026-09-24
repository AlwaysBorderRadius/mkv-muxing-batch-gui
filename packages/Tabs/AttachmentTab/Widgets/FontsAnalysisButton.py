from PySide6.QtWidgets import QPushButton

from packages.Tabs.AttachmentTab.Widgets.FontsAnalysisDialog import (
    FontsAnalysisDialog,
)
from packages.Tabs.GlobalSetting import GlobalSetting


class FontsAnalysisButton(QPushButton):
    def __init__(self):
        super().__init__()
        self.hint_when_enabled = (
            "<nobr>Show which attached fonts are actually used by the subtitles "
            "of each episode, and preview the result of the 'Attach Only Fonts Used "
            "by Subtitles' / 'Trim non-Latin Letters' options.<br>This only "
            "analyzes; it does not change any muxy settings."
        )
        self.setText("Fonts Analysis")
        self.setToolTip(self.hint_when_enabled)
        self.clicked.connect(self.open_fonts_analysis_dialog)

    def open_fonts_analysis_dialog(self):
        dialog = FontsAnalysisDialog(parent=self.window())
        dialog.execute()

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
