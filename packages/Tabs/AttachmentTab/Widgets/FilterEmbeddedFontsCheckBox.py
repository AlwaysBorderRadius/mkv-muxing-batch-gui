from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox

from packages.Startup.Options import save_options
from packages.Tabs.GlobalSetting import GlobalSetting


class FilterEmbeddedFontsCheckBox(QCheckBox):
    is_checked_signal = Signal(bool)

    def __init__(self):
        super().__init__()
        self.hint_when_enabled = (
            "Extract the fonts embedded in each MKV and filter them against the "
            "subtitles like your folder fonts.<br>"
            "Both your external subtitles and the MKV's own embedded subtitles are "
            "used to decide which families to keep.<br>"
            "The MKV's original attachments are discarded and only the kept fonts "
            "are re-attached<br>"
            "(this automatically enables 'Discard Old Attachments')."
        )
        self.hint_filter_required = (
            "<br>Requires '<b>Attach Only Fonts Used by Subtitles</b>' to be enabled"
        )
        self.setText("Filter Embedded Fonts")
        self.embedded_available = False
        self.queue_enabled = False
        self.toggled.connect(self.change_global_filter_embedded_fonts)
        self.setToolTip(self.hint_when_enabled)

    # noinspection PyMethodMayBeStatic
    def change_global_filter_embedded_fonts(self, new_state):
        GlobalSetting.ATTACHMENT_FILTER_EMBEDDED_FONTS = new_state
        self.is_checked_signal.emit(new_state)
        save_options()

    def set_embedded_available(self, available: bool):
        self.embedded_available = available
        self.refresh_enabled_state()

    def refresh_enabled_state(self):
        super().setEnabled(self.queue_enabled and self.embedded_available)
        queued_disabled = not self.queue_enabled and not GlobalSetting.JOB_QUEUE_EMPTY
        tool_tip = self.hint_when_enabled
        if not self.embedded_available:
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
