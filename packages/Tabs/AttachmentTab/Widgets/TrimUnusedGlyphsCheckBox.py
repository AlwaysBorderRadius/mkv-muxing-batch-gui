from PySide6.QtWidgets import QCheckBox

from packages.Startup.Options import save_options
from packages.Tabs.GlobalSetting import GlobalSetting


class TrimUnusedGlyphsCheckBox(QCheckBox):
    def __init__(self):
        super().__init__()
        self.hint_when_enabled = (
            "Keeps every Latin letter plus the characters the subtitles actually "
            "use.<br>"
            "Drops the non-Latin glyphs the subtitles do not use."
        )
        self.hint_filter_required = (
            "<br>Requires '<b>Attach Only Fonts Used by Subtitles</b>' to be enabled"
        )
        self.setText("Trim non-Latin Letters")
        self.trim_available = False
        self.queue_enabled = False
        self.toggled.connect(self.change_global_trim_unused_glyphs)
        self.setToolTip(self.hint_when_enabled)

    # noinspection PyMethodMayBeStatic
    def change_global_trim_unused_glyphs(self, new_state):
        GlobalSetting.ATTACHMENT_TRIM_UNUSED_GLYPHS = new_state
        save_options()

    def set_trim_available(self, available: bool):
        self.trim_available = available
        self.refresh_enabled_state()

    def refresh_enabled_state(self):
        super().setEnabled(self.queue_enabled and self.trim_available)
        queued_disabled = not self.queue_enabled and not GlobalSetting.JOB_QUEUE_EMPTY
        tool_tip = self.hint_when_enabled
        if not self.trim_available:
            tool_tip += self.hint_filter_required
        elif queued_disabled:
            tool_tip += "<br>" + GlobalSetting.DISABLE_TOOLTIP
        super().setToolTip(tool_tip)

    def setEnabled(self, new_state: bool):
        self.queue_enabled = new_state
        self.refresh_enabled_state()

    def setDisabled(self, new_state: bool):
        self.queue_enabled = not new_state
        self.refresh_enabled_state()

    def setToolTip(self, new_tool_tip: str):
        if self.isEnabled() or GlobalSetting.JOB_QUEUE_EMPTY:
            self.hint_when_enabled = new_tool_tip
        super().setToolTip(new_tool_tip)
