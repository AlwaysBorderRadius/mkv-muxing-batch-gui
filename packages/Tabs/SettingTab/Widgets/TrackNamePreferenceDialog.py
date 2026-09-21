from PySide6 import QtGui
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from packages.Widgets.ListWidget import ListWidget
from packages.Widgets.MyDialog import MyDialog


class TrackNamePreferenceDialog(MyDialog):
    def __init__(self, old_favorite, parent=None):
        super().__init__(parent)
        self.old_favorite = old_favorite
        self.current_favorite = self.old_favorite.copy()
        self.setWindowTitle("Subtitle Track Names Preference")
        self.track_names_label = QLabel("Favorite Subtitle Track Names:")
        self.track_names_list = ListWidget()
        self.track_names_list.addItems(self.old_favorite)
        self.track_names_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.new_track_name_label = QLabel("New name:")
        self.new_track_name_lineEdit = QLineEdit()
        self.new_track_name_lineEdit.setClearButtonEnabled(True)
        self.add_name_button = QPushButton("Add")
        self.remove_names_button = QPushButton("Remove Selected")
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        self.selected_items_from_track_names = []
        self.add_name_layout = QHBoxLayout()
        self.list_buttons_layout = QHBoxLayout()
        self.dialog_buttons_layout = QHBoxLayout()
        self.main_layout = QVBoxLayout()
        self.setup_add_name_layout()
        self.setup_list_buttons_layout()
        self.setup_dialog_buttons_layout()
        self.setup_main_layout()
        self.disable_question_mark_window()
        self.signal_connect()
        self.new_track_name_lineEdit.setFocus()

    def setup_add_name_layout(self):
        self.add_name_layout.addWidget(self.new_track_name_label)
        self.add_name_layout.addWidget(self.new_track_name_lineEdit, stretch=1)
        self.add_name_layout.addWidget(self.add_name_button)

    def setup_list_buttons_layout(self):
        self.list_buttons_layout.addStretch()
        self.list_buttons_layout.addWidget(self.remove_names_button)
        self.remove_names_button.setEnabled(False)

    def setup_dialog_buttons_layout(self):
        self.dialog_buttons_layout.addStretch()
        self.dialog_buttons_layout.addWidget(self.ok_button)
        self.dialog_buttons_layout.addWidget(self.cancel_button)
        self.dialog_buttons_layout.addStretch()

    def setup_main_layout(self):
        self.main_layout.addWidget(self.track_names_label)
        self.main_layout.addWidget(self.track_names_list)
        self.main_layout.addLayout(self.list_buttons_layout)
        self.main_layout.addLayout(self.add_name_layout)
        self.main_layout.addLayout(self.dialog_buttons_layout)
        self.setLayout(self.main_layout)
        self.track_names_list.clearSelection()

    def signal_connect(self):
        self.ok_button.clicked.connect(self.click_yes)
        self.cancel_button.clicked.connect(self.click_no)
        self.add_name_button.clicked.connect(self.add_name_button_clicked)
        self.new_track_name_lineEdit.returnPressed.connect(self.add_name_button_clicked)
        self.remove_names_button.clicked.connect(self.remove_names_button_clicked)
        self.track_names_list.itemSelectionChanged.connect(
            self.update_selected_track_names_selected
        )

    def update_selected_track_names_selected(self):
        self.selected_items_from_track_names = [
            item.text() for item in self.track_names_list.selectedItems()
        ]
        self.remove_names_button.setEnabled(len(self.selected_items_from_track_names) > 0)

    def add_name_button_clicked(self):
        new_name = self.new_track_name_lineEdit.text().strip()
        if new_name == "":
            return
        for i in range(self.track_names_list.count()):
            if self.track_names_list.item(i).text() == new_name:
                return
        self.track_names_list.addItem(new_name)
        self.new_track_name_lineEdit.clear()
        self.new_track_name_lineEdit.setFocus()

    def remove_names_button_clicked(self):
        for item in list(self.track_names_list.selectedItems()):
            self.track_names_list.takeItem(self.track_names_list.row(item))
        self.setup_new_items_after_removal()

    def setup_new_items_after_removal(self):
        self.selected_items_from_track_names = []
        self.remove_names_button.setEnabled(False)
        self.track_names_list.clearSelection()

    def click_yes(self):
        self.current_favorite = []
        for i in range(self.track_names_list.count()):
            self.current_favorite.append(self.track_names_list.item(i).text())
        self.close()

    def click_no(self):
        self.current_favorite = self.old_favorite.copy()
        self.close()

    def showEvent(self, a0: QtGui.QShowEvent) -> None:
        super().showEvent(a0)
        self.setFixedSize(QSize(self.size().width() + 30, self.size().height()))

    def disable_question_mark_window(self):
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, on=False)

    def execute(self):
        self.exec()
