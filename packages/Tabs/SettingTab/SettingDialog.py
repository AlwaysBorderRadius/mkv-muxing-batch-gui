# import faulthandler
from PySide6 import QtGui
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QGroupBox,
    QLineEdit,
)
from packages.Startup.Options import (
    Options,
    save_options,
    get_names_list_of_presets,
    parse_keywords_text,
    DEFAULT_SUBTITLE_KARAOKE_STYLE_KEYWORDS,
    DEFAULT_SUBTITLE_KARAOKE_EFFECT_KEYWORDS,
)
from packages.Startup.SubtitleStartTimeSync import invalidate_subtitle_cue_cache
from packages.Startup.GlobalFiles import InfoIconPath
from packages.Startup.GlobalIcons import SettingIcon
from packages.Startup.InitializeScreenResolution import screen_size
from packages.Tabs.SettingTab.Widgets.AboutButton import AboutButton
from packages.Tabs.SettingTab.Widgets.PresetTabComboBox import PresetTabComboBox
from packages.Tabs.SettingTab.Widgets.PresetTabDeleteButton import PresetTabDeleteButton
from packages.Tabs.SettingTab.Widgets.PresetTabRenameButton import PresetTabRenameButton
from packages.Tabs.SettingTab.Widgets.PresetTabSetDeafultButton import (
    PresetTabSetDefaultButton,
)
from packages.Tabs.SettingTab.Widgets.PresetTabWidget import PresetTabWidget
from packages.Tabs.SettingTab.Widgets.TrackNamePreferenceDialog import (
    TrackNamePreferenceDialog,
)
from packages.Widgets.MyDialog import MyDialog
from packages.Widgets.SingleDefaultPresetsData import SingleDefaultPresetsData

# faulthandler.enable()


class SettingDialog(MyDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(SettingIcon)
        self.setWindowTitle("Options")
        self.setMinimumWidth(screen_size.width() // 1.9)
        self.message = QLabel()
        self.extra_message = QLabel()
        self.yes_button = QPushButton("OK")
        self.no_button = QPushButton("Cancel")
        self.setting_info_text_icon_label = QLabel()
        self.setting_info_text_icon_pixmap = QPixmap(InfoIconPath)
        self.setting_info_text_icon_label.setPixmap(self.setting_info_text_icon_pixmap)
        self.setting_info_text_label = QLabel("Changes will take effect on next launch")
        self.setting_about_button = AboutButton()

        self.preset_tabs = []
        self.preset_counter = 0
        self.preset_tab_label = QLabel("Presets: ")
        self.preset_tab_comboBox = PresetTabComboBox(
            items=get_names_list_of_presets(),
            activated_preset_id=Options.FavoritePresetId,
        )
        self.preset_tab_delete_button = PresetTabDeleteButton()
        self.preset_tab_rename_button = PresetTabRenameButton()
        self.preset_tab_set_default_button = PresetTabSetDefaultButton()
        self.preset_tab_ask_on_start_check_box = QCheckBox("Ask for preset on startup")
        self.karaoke_settings_groupBox = QGroupBox("Subtitle Start-Time Detection")
        self.karaoke_tag_filter_check_box = QCheckBox(
            "Detect karaoke lines by {\\k...} override tags"
        )
        self.karaoke_style_keywords_label = QLabel("Style keywords (comma separated):")
        self.karaoke_style_keywords_lineEdit = QLineEdit()
        self.karaoke_style_keywords_lineEdit.setToolTip(
            "Lines whose style contains one of these keywords are treated as karaoke.\n"
            "Defaults: "
            + ", ".join(DEFAULT_SUBTITLE_KARAOKE_STYLE_KEYWORDS)
            + "\n\nEmpty list = style filter disabled"
        )
        self.karaoke_style_keywords_reset_button = QPushButton("Reset")
        self.karaoke_style_keywords_reset_button.setToolTip(
            "Restore default style keywords"
        )
        self.karaoke_effect_keywords_label = QLabel("Effect keywords (comma separated):")
        self.karaoke_effect_keywords_lineEdit = QLineEdit()
        self.karaoke_effect_keywords_lineEdit.setToolTip(
            "Lines whose effect contains one of these keywords are treated as karaoke.\n"
            "Defaults: "
            + ", ".join(DEFAULT_SUBTITLE_KARAOKE_EFFECT_KEYWORDS)
            + "\n\nEmpty list = effect filter disabled"
        )
        self.karaoke_effect_keywords_reset_button = QPushButton("Reset")
        self.karaoke_effect_keywords_reset_button.setToolTip(
            "Restore default effect keywords"
        )

        self.karaoke_style_keywords_lineEdit.setText(
            ", ".join(Options.Subtitle_Karaoke_Style_Keywords)
        )
        self.karaoke_effect_keywords_lineEdit.setText(
            ", ".join(Options.Subtitle_Karaoke_Effect_Keywords)
        )
        self.karaoke_tag_filter_check_box.setChecked(Options.Subtitle_Karaoke_Tag_Filter)
        self.track_names_groupBox = QGroupBox("Favorite Subtitle Track Names")
        self.track_names_label = QLabel("Favorite Subtitle Track Names:")
        self.track_names_preview_lineEdit = QLineEdit()
        self.track_names_preview_lineEdit.setReadOnly(True)
        self.track_names_manage_button = QPushButton()
        self.track_names_manage_button.setIcon(SettingIcon)
        self.track_names_manage_button.setText("Manage...")
        self.track_names_manage_button.setToolTip(
            "Manage the subtitle track names shown in the Subtitle tab Track Name dropdown"
        )
        self.update_track_names_preview()
        self.preset_tab_setting_layout = QHBoxLayout()
        self.current_tab_index = 0
        self.current_preset_tab = None
        self.setup_presets()
        self.preset_tab_setting_layout.addWidget(self.preset_tab_label)
        self.preset_tab_setting_layout.addWidget(self.preset_tab_comboBox)
        self.preset_tab_setting_layout.addWidget(self.preset_tab_rename_button)
        self.preset_tab_setting_layout.addWidget(self.preset_tab_delete_button)
        self.preset_tab_setting_layout.addWidget(self.preset_tab_set_default_button)
        self.preset_tab_setting_layout.addStretch(200)
        self.preset_tab_setting_layout.addWidget(self.preset_tab_ask_on_start_check_box)
        self.preset_tab_setting_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.addStretch(stretch=3)
        self.buttons_layout.addWidget(self.yes_button, stretch=2)
        self.buttons_layout.addWidget(self.no_button, stretch=2)
        self.buttons_layout.addStretch(stretch=3)

        self.setting_info_layout = QHBoxLayout()
        self.setting_info_layout.addWidget(self.setting_info_text_icon_label, stretch=0)
        self.setting_info_layout.addWidget(self.setting_info_text_label, stretch=1)
        self.setting_info_layout.addWidget(
            self.setting_about_button, stretch=0, alignment=Qt.AlignmentFlag.AlignRight
        )

        self.karaoke_settings_layout = QGridLayout()
        self.karaoke_settings_layout.addWidget(
            self.karaoke_tag_filter_check_box, 0, 0, 1, 3
        )
        self.karaoke_settings_layout.addWidget(self.karaoke_style_keywords_label, 1, 0)
        self.karaoke_settings_layout.addWidget(self.karaoke_style_keywords_lineEdit, 1, 1)
        self.karaoke_settings_layout.addWidget(
            self.karaoke_style_keywords_reset_button, 1, 2
        )
        self.karaoke_settings_layout.addWidget(self.karaoke_effect_keywords_label, 2, 0)
        self.karaoke_settings_layout.addWidget(
            self.karaoke_effect_keywords_lineEdit, 2, 1
        )
        self.karaoke_settings_layout.addWidget(
            self.karaoke_effect_keywords_reset_button, 2, 2
        )
        self.karaoke_settings_layout.setColumnStretch(0, 0)
        self.karaoke_settings_layout.setColumnStretch(1, 1)
        self.karaoke_settings_layout.setColumnStretch(2, 0)
        self.karaoke_settings_layout.setContentsMargins(5, 5, 5, 5)
        self.karaoke_settings_groupBox.setLayout(self.karaoke_settings_layout)

        self.track_names_layout = QHBoxLayout()
        self.track_names_layout.addWidget(self.track_names_label, stretch=0)
        self.track_names_layout.addWidget(self.track_names_preview_lineEdit, stretch=1)
        self.track_names_layout.addWidget(self.track_names_manage_button, stretch=0)
        self.track_names_layout.setContentsMargins(5, 5, 5, 5)
        self.track_names_groupBox.setLayout(self.track_names_layout)

        self.main_layout = QGridLayout()
        self.main_layout.addLayout(self.preset_tab_setting_layout, 0, 0, 1, 1)
        self.main_layout.addWidget(self.karaoke_settings_groupBox, 1, 0, 1, 1)
        self.main_layout.addWidget(self.track_names_groupBox, 2, 0, 1, 1)
        self.main_layout.addWidget(self.current_preset_tab, 3, 0, 1, 1)
        self.main_layout.addLayout(self.setting_info_layout, 4, 0, 1, 1)
        self.main_layout.addLayout(self.buttons_layout, 5, 0, 1, 1)

        self.main_layout.setRowStretch(1, 0)
        self.main_layout.setRowStretch(2, 0)
        self.main_layout.setRowStretch(3, 0)
        self.main_layout.setRowStretch(4, 0)
        self.main_layout.setRowStretch(5, 0)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(self.main_layout)

        self.result = "No"
        self.setup_ui()
        self.signal_connect()

    def setup_presets(self):
        self.preset_tab_comboBox.setCurrentIndex(Options.FavoritePresetId)
        self.preset_tab_comboBox.updateText(self.preset_tab_comboBox.currentText())
        for preset_id in range(len(Options.DefaultPresets)):
            self.preset_tabs.append(PresetTabWidget(Options.DefaultPresets[preset_id]))
            self.preset_counter += 1
        self.current_tab_index = Options.FavoritePresetId
        self.current_preset_tab = self.preset_tabs[self.current_tab_index]
        self.preset_tab_ask_on_start_check_box.setChecked(
            Options.Choose_Preset_On_Startup
        )
        self.update_rename_button_current_tab_name()

    def setup_ui(self):
        self.disable_question_mark_window()

    def signal_connect(self):
        self.yes_button.clicked.connect(self.click_yes)
        self.no_button.clicked.connect(self.click_no)
        self.preset_tab_comboBox.current_tab_changed_signal.connect(
            self.change_current_preset_tab
        )
        self.preset_tab_comboBox.create_new_tab_signal.connect(self.create_new_preset_tab)
        self.preset_tab_delete_button.remove_tab_signal.connect(self.delete_current_tab)
        self.preset_tab_rename_button.rename_tab_signal.connect(
            self.update_current_preset_name
        )
        self.preset_tab_set_default_button.set_active_preset_signal.connect(
            self.update_default_preset
        )
        self.karaoke_style_keywords_reset_button.clicked.connect(
            self.reset_karaoke_style_keywords
        )
        self.karaoke_effect_keywords_reset_button.clicked.connect(
            self.reset_karaoke_effect_keywords
        )
        self.track_names_manage_button.clicked.connect(
            self.manage_track_names_button_clicked
        )

    def update_track_names_preview(self):
        self.track_names_preview_lineEdit.setText(
            ", ".join(Options.Subtitle_Favorite_Track_Names)
        )

    def manage_track_names_button_clicked(self):
        track_names_preference_dialog = TrackNamePreferenceDialog(
            old_favorite=Options.Subtitle_Favorite_Track_Names,
            parent=self,
        )
        track_names_preference_dialog.execute()
        Options.Subtitle_Favorite_Track_Names = (
            track_names_preference_dialog.current_favorite.copy()
        )
        self.update_track_names_preview()

    def reset_karaoke_style_keywords(self):
        self.karaoke_style_keywords_lineEdit.setText(
            ", ".join(DEFAULT_SUBTITLE_KARAOKE_STYLE_KEYWORDS)
        )

    def reset_karaoke_effect_keywords(self):
        self.karaoke_effect_keywords_lineEdit.setText(
            ", ".join(DEFAULT_SUBTITLE_KARAOKE_EFFECT_KEYWORDS)
        )

    def click_yes(self):
        self.result = "Yes"
        self.save_new_settings()
        self.close()

    def click_no(self):
        self.result = "No"
        self.close()

    def save_new_settings(self):
        default_options = []
        for preset_id in range(self.preset_counter):
            temp_default_options = self.preset_tabs[
                preset_id
            ].get_current_options_as_option_data()
            temp_default_options.Preset_Name = self.preset_tab_comboBox.itemText(
                preset_id
            )
            default_options.append(temp_default_options)
        Options.DefaultPresets = default_options.copy()
        Options.Choose_Preset_On_Startup = (
            self.preset_tab_ask_on_start_check_box.isChecked()
        )
        Options.Subtitle_Karaoke_Tag_Filter = (
            self.karaoke_tag_filter_check_box.isChecked()
        )
        Options.Subtitle_Karaoke_Style_Keywords = parse_keywords_text(
            self.karaoke_style_keywords_lineEdit.text()
        )
        Options.Subtitle_Karaoke_Effect_Keywords = parse_keywords_text(
            self.karaoke_effect_keywords_lineEdit.text()
        )
        Options.FavoritePresetId = self.preset_tab_comboBox.activated_preset_id
        save_options()
        invalidate_subtitle_cue_cache()

    def change_current_preset_tab(self, tab_index):
        self.main_layout.replaceWidget(
            self.current_preset_tab, self.preset_tabs[tab_index]
        )
        self.current_preset_tab.hide()
        self.preset_tabs[tab_index].show()
        self.current_preset_tab = self.preset_tabs[tab_index]
        # if tab_index == 0:
        #     self.preset_tab_delete_button.hide()
        # else:
        #     self.preset_tab_delete_button.show()
        self.current_tab_index = tab_index
        self.update_rename_button_current_tab_name()
        if tab_index != self.preset_tab_comboBox.activated_preset_id:
            self.preset_tab_set_default_button.set_activated()
        else:
            self.preset_tab_set_default_button.set_disabled()

    def update_rename_button_current_tab_name(self):
        self.preset_tab_rename_button.current_preset_name = (
            self.preset_tab_comboBox.currentText()
        )

    def create_new_preset_tab(self):
        self.preset_tabs.append(PresetTabWidget(SingleDefaultPresetsData()))
        self.main_layout.replaceWidget(self.current_preset_tab, self.preset_tabs[-1])
        self.current_preset_tab.hide()
        self.preset_tabs[-1].show()
        self.current_preset_tab = self.preset_tabs[-1]
        self.preset_counter += 1
        self.current_tab_index = self.preset_counter - 1
        self.update_rename_button_current_tab_name()
        if self.preset_counter >= 2:
            self.preset_tab_delete_button.show()
        self.preset_tab_set_default_button.set_activated()

    def delete_current_tab(self):
        self.preset_counter -= 1
        index_to_delete = self.current_tab_index
        if index_to_delete != 0:
            to_switch_tab_index = index_to_delete - 1
            self.current_tab_index = to_switch_tab_index
        else:
            to_switch_tab_index = index_to_delete + 1
            self.current_tab_index = index_to_delete
        self.main_layout.replaceWidget(
            self.preset_tabs[index_to_delete], self.preset_tabs[to_switch_tab_index]
        )
        self.preset_tab_comboBox.delete_tab(
            index_to_remove=index_to_delete, new_selected_index=self.current_tab_index
        )
        self.preset_tabs[index_to_delete].hide()
        self.preset_tabs[index_to_delete].deleteLater()
        del self.preset_tabs[index_to_delete]
        self.current_preset_tab = self.preset_tabs[self.current_tab_index]
        self.current_preset_tab.show()
        self.update_rename_button_current_tab_name()
        if self.preset_counter >= 2:
            self.preset_tab_delete_button.show()
        else:
            self.preset_tab_delete_button.hide()

    def update_current_preset_name(self, new_name):
        self.preset_tab_comboBox.setItemText(self.current_tab_index, new_name)
        self.preset_tab_comboBox.updateText(new_name)
        self.update_rename_button_current_tab_name()

    def update_default_preset(self):
        new_default_preset_id = self.preset_tab_comboBox.currentIndex()
        self.preset_tab_set_default_button.set_disabled()
        self.preset_tab_comboBox.set_activated_preset_id(new_default_preset_id)
        self.preset_tab_comboBox.updateText(self.preset_tab_comboBox.currentText())

    def showEvent(self, a0: QtGui.QShowEvent) -> None:
        super().showEvent(a0)
        self.setFixedHeight(self.size().height())

    def disable_question_mark_window(self):
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, on=False)

    def execute(self):
        if self.preset_counter >= 2:
            self.preset_tab_delete_button.show()
        else:
            self.preset_tab_delete_button.hide()
        self.exec()
