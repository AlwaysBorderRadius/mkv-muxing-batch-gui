import os
from pathlib import Path

from PySide6.QtCore import QEvent, QRect, QSize, Qt, QThread, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
    QVBoxLayout,
)

from packages.Tabs.AttachmentTab import FontAnalysis
from packages.Tabs.GlobalSetting import GlobalSetting, get_readable_filesize
from packages.Widgets.MyDialog import MyDialog

WARNING_STYLE = (
    "background-color: #c62828; color: white; padding: 6px; border-radius: 4px;"
)
INFO_STYLE = "background-color: #1565C0; color: white; padding: 6px; border-radius: 4px;"

FONT_ENTRIES_ROLE = Qt.ItemDataRole.UserRole


def _total_size(paths) -> int:
    total = 0
    for file_path in paths:
        try:
            total += os.path.getsize(file_path)
        except Exception:
            continue
    return total


def _is_ass_or_ssa(path: Path) -> bool:
    return path.suffix.lower() in (".ass", ".ssa")


def get_episode_rows() -> int:
    video_rows = len(GlobalSetting.VIDEO_FILES_LIST)
    subtitle_rows = 0
    for subtitle_list in GlobalSetting.SUBTITLE_FILES_ABSOLUTE_PATH_LIST.values():
        subtitle_rows = max(subtitle_rows, len(subtitle_list))
    return max(video_rows, subtitle_rows)


def get_checked_attachment_paths() -> list[str]:
    result = []
    for i in range(len(GlobalSetting.ATTACHMENT_FILES_ABSOLUTE_PATH_LIST)):
        if GlobalSetting.ATTACHMENT_FILES_CHECKING_LIST[i]:
            result.append(GlobalSetting.ATTACHMENT_FILES_ABSOLUTE_PATH_LIST[i])
    return result


def get_all_attachment_paths() -> list[str]:
    if GlobalSetting.ATTACHMENT_EXPERT_MODE:
        result = []
        for path_data in GlobalSetting.ATTACHMENT_PATH_DATA_LIST:
            result.extend(path_data.files_list)
        return result
    return get_checked_attachment_paths()


class SeriesSummaryWorker(QThread):
    finished_signal = Signal(dict)

    def __init__(self, attachment_paths, parent=None):
        super().__init__(parent)
        self.attachment_paths = list(attachment_paths)
        self.result = {}

    def run(self):
        result = {}
        used_families = set()
        for tab_index in GlobalSetting.SUBTITLE_FILES_ABSOLUTE_PATH_LIST:
            for subtitle_path in GlobalSetting.SUBTITLE_FILES_ABSOLUTE_PATH_LIST[
                tab_index
            ]:
                if not subtitle_path:
                    continue
                single_path = Path(subtitle_path)
                if not _is_ass_or_ssa(single_path):
                    continue
                try:
                    families, _, _ = FontAnalysis.get_subtitle_font_usage(single_path)
                except Exception:
                    continue
                used_families.update(families)
        existing_paths = [
            Path(file_path)
            for file_path in self.attachment_paths
            if file_path and os.path.isfile(file_path)
        ]
        attachment_families = FontAnalysis.get_families_in_attachments(existing_paths)
        missing = set(used_families) - attachment_families
        result["families"] = sorted(used_families)
        result["missing_custom"] = sorted(
            family for family in missing if not FontAnalysis.is_common_system_font(family)
        )
        result["missing_system"] = sorted(
            family for family in missing if FontAnalysis.is_common_system_font(family)
        )
        result["total_count"] = len(existing_paths)
        result["total_size"] = _total_size(existing_paths)
        unique_paths = FontAnalysis.dedupe_attachments(existing_paths)
        result["unique_count"] = len(unique_paths)
        result["unique_size"] = _total_size(unique_paths)
        used_paths = set()
        for episode_index in range(get_episode_rows()):
            episode_groups = FontAnalysis.get_episode_subtitle_groups(episode_index)
            episode_subtitle_paths = [path for _, path in episode_groups]
            if not episode_subtitle_paths:
                continue
            if GlobalSetting.ATTACHMENT_EXPERT_MODE:
                if len(GlobalSetting.ATTACHMENT_PATH_DATA_LIST) > episode_index:
                    source = GlobalSetting.ATTACHMENT_PATH_DATA_LIST[
                        episode_index
                    ].files_list.copy()
                else:
                    source = []
            else:
                source = existing_paths
            if not source:
                continue
            kept = FontAnalysis.filter_and_trim_attachments(
                source, episode_subtitle_paths, True, False
            )
            used_paths.update(str(path) for path in kept)
        result["used_count"] = len(used_paths)
        result["used_size"] = _total_size(used_paths)
        self.result = result
        self.finished_signal.emit(result)


class FontsAnalysisDialog(MyDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fonts Analysis")
        self.setModal(True)
        self.resize(980, 640)

        self.episode_combo = QComboBox()
        self.episode_combo.currentIndexChanged.connect(self.refresh_episode)

        self.banner_label = QLabel("")
        self.banner_label.setWordWrap(True)
        self.banner_label.hide()

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Subtitle Group", "Fonts", "Evidence"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Interactive
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.table.setColumnWidth(0, 300)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.viewport().installEventFilter(self)

        self.episode_info_label = QLabel("")
        self.episode_info_label.setWordWrap(True)

        self.global_info_label = QLabel("")
        self.global_info_label.setWordWrap(True)
        self.global_info_label.setStyleSheet("color: #807F7F;")

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)

        self.top_layout = QHBoxLayout()
        self.top_layout.addWidget(QLabel("Episode:"))
        self.top_layout.addWidget(self.episode_combo, 1)

        self.main_layout = QVBoxLayout()
        self.main_layout.addLayout(self.top_layout)
        self.main_layout.addWidget(self.banner_label)
        self.main_layout.addWidget(self.table, 1)
        self.main_layout.addWidget(self.episode_info_label)
        self.main_layout.addWidget(self.global_info_label)
        self.main_layout.addWidget(
            self.close_button, alignment=Qt.AlignmentFlag.AlignRight
        )
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(self.main_layout)

        self.attachment_paths = get_checked_attachment_paths()
        self.episode_count = get_episode_rows()

        if self.episode_count > 0:
            episode_labels = []
            for i in range(self.episode_count):
                if i < len(GlobalSetting.VIDEO_FILES_LIST):
                    episode_labels.append(Path(GlobalSetting.VIDEO_FILES_LIST[i]).name)
                else:
                    episode_labels.append(f"Episode {i + 1} (no video)")
            self.episode_combo.addItems(episode_labels)
            self.episode_combo.setCurrentIndex(0)
        else:
            self.episode_combo.setEnabled(False)
            self.global_info_label.setText(
                "No videos or subtitles loaded. Open the Video/Subtitle/Groups "
                "tabs to see the per-episode font breakdown."
            )

        self.worker = SeriesSummaryWorker(get_all_attachment_paths(), parent=self)
        self.worker.finished_signal.connect(self.update_global_info)
        self.worker.start()

        self.refresh_episode()

    def refresh_episode(self, *_):
        self.banner_label.hide()
        self.table.clearContents()
        episode_index = self.episode_combo.currentIndex()
        if self.episode_count == 0 or episode_index < 0:
            self.episode_info_label.setText("")
            return
        if GlobalSetting.ATTACHMENT_EXPERT_MODE:
            if len(GlobalSetting.ATTACHMENT_PATH_DATA_LIST) > episode_index:
                attachment_paths = GlobalSetting.ATTACHMENT_PATH_DATA_LIST[
                    episode_index
                ].files_list.copy()
            else:
                attachment_paths = []
        else:
            attachment_paths = self.attachment_paths
        subtitle_groups = FontAnalysis.get_episode_subtitle_groups(episode_index)
        info = FontAnalysis.analyze_subtitle_groups(attachment_paths, subtitle_groups)
        self.update_fonts_table(info)

        filter_enabled = GlobalSetting.ATTACHMENT_FILTER_UNUSED_FONTS
        trim_enabled = GlobalSetting.ATTACHMENT_TRIM_UNUSED_GLYPHS
        total_size = get_readable_filesize(size_bytes=_total_size(attachment_paths))
        episode_label = self.episode_combo.currentText()
        if not filter_enabled:
            info_message = (
                f"{episode_label}: the 'Attach Only Fonts Used by Subtitles' option "
                "is off, so all attached fonts would be muxed "
                f"({len(attachment_paths)} files, {total_size})."
            )
        else:
            subtitle_paths = [path for _, path in subtitle_groups]
            kept = FontAnalysis.filter_and_trim_attachments(
                attachment_paths, subtitle_paths, True, False
            )
            kept_size = get_readable_filesize(size_bytes=_total_size(kept))
            if trim_enabled:
                final = FontAnalysis.filter_and_trim_attachments(
                    attachment_paths, subtitle_paths, True, True
                )
                final_size = get_readable_filesize(size_bytes=_total_size(final))
                info_message = (
                    f"{episode_label} keeps {len(kept)} of {len(attachment_paths)} "
                    f"fonts ({kept_size} instead of {total_size})\n"
                    f"trimmed {len(final)} of {len(kept)} files "
                    f"({final_size} instead of {kept_size})"
                )
            else:
                info_message = (
                    f"{episode_label} keeps {len(kept)} of {len(attachment_paths)} "
                    f"fonts ({kept_size} instead of {total_size})"
                )
        self.episode_info_label.setText(info_message)

        missing_custom = info["missing_custom"]
        missing_system = info["missing_system"]
        if missing_custom:
            banner_text = (
                "Fonts used by these subtitles but not attached, and not "
                "standard system fonts:\n" + ", ".join(missing_custom)
            )
            self.banner_label.setStyleSheet(WARNING_STYLE)
            self.banner_label.setText(banner_text)
            self.banner_label.show()
        elif missing_system:
            banner_text = (
                "Standard system fonts used (not attached; the player will use "
                "its local fallback):\n" + ", ".join(missing_system)
            )
            self.banner_label.setStyleSheet(INFO_STYLE)
            self.banner_label.setText(banner_text)
            self.banner_label.show()

    def update_fonts_table(self, info):
        groups = info["groups"]
        self.table.setRowCount(len(groups))
        for group_index, group in enumerate(groups):
            group_path = group["path"]
            group_name = Path(group_path).name
            tab_index = group["tab_index"]
            track_name = GlobalSetting.SUBTITLE_TRACK_NAME.get(tab_index, "")
            language = GlobalSetting.SUBTITLE_LANGUAGE.get(tab_index, "")
            header_text = group_name
            if language:
                header_text += "   [" + language + "]"
            if track_name and track_name not in (group_name, ""):
                header_text += "   " + track_name
            header_item = QTableWidgetItem(header_text)
            header_item.setToolTip(group_path)
            header_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            self.table.setItem(group_index, 0, header_item)

            fonts_text = ""
            evidence_text = ""
            families = sorted(group["families"])
            if not families:
                fonts_text = "(no usable font info; if only SRT/PGS, all fonts are kept)"
                evidence_text = "—"
                entries = []
            else:
                family_lines = []
                evidence_lines = []
                entries = []
                family_files = info["family_files"]
                for family in sorted(families):
                    evidence = group["evidence"].get(family, {})
                    if family in info["attachment_families"]:
                        for item in family_files[family]:
                            family_lines.append("✓  " + item["display"])
                            entries.append(
                                {
                                    "kind": "file",
                                    "text": "✓  " + item["display"],
                                    "name": item["display"],
                                    "file": item["file"],
                                    "family": family,
                                    "repeats": item["repeats"],
                                }
                            )
                    elif family in info["missing_custom"]:
                        mark = "✗"
                        family_lines.append(mark + "  " + family)
                        entries.append(
                            {"kind": "family", "text": "✗  " + family, "family": family}
                        )
                    else:
                        mark = "⚠"
                        family_lines.append(mark + "  " + family)
                        entries.append(
                            {"kind": "family", "text": "⚠  " + family, "family": family}
                        )
                    evidence_lines.extend(
                        f"{family} — {mechanism}"
                        for mechanism in self._evidence_mechanisms(evidence)
                    )
                fonts_text = "\n".join(family_lines)
                evidence_text = "\n".join(evidence_lines)
            fonts_item = QTableWidgetItem(fonts_text)
            evidence_item = QTableWidgetItem(evidence_text)
            fonts_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            evidence_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            fonts_item.setData(FONT_ENTRIES_ROLE, entries)
            self.table.setItem(group_index, 1, fonts_item)
            self.table.setItem(group_index, 2, evidence_item)
        self._fit_table_rows()

    def _fit_table_rows(self):
        for row in range(self.table.rowCount()):
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                if item is None:
                    continue
                text = item.text()
                if not text:
                    continue
                font_metrics = QFontMetrics(item.font())
                width = max(self.table.columnWidth(column) - 14, 80)
                rect = font_metrics.boundingRect(
                    QRect(0, 0, width, 1 << 30),
                    Qt.TextWordWrap | Qt.AlignmentFlag.AlignLeft,
                    text,
                )
                item.setSizeHint(QSize(width, rect.height() + 6))
        self.table.resizeRowsToContents()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        table = getattr(self, "table", None)
        if table is not None and table.rowCount() > 0:
            self._fit_table_rows()

    def _evidence_mechanisms(self, evidence) -> list[str]:
        mechanisms = []
        style_counts = evidence.get("styles")
        if style_counts:
            for style, count in sorted(style_counts.items()):
                mechanisms.append(
                    f"Style '{style}' -> Fontname field -> {count} dialogue lines"
                )
        fn_count = evidence.get("fn_count", 0)
        if fn_count:
            mechanisms.append(f"\\fn override in the Text field -> {fn_count}")
        reset_counts = evidence.get("resets")
        if reset_counts:
            for style, count in sorted(reset_counts.items()):
                mechanisms.append(
                    f"\\r reset to Style '{style}' -> Fontname field -> {count}"
                )
        if evidence.get("fallback"):
            mechanisms.append("fallback: no parseable events, all styles counted")
        return mechanisms or ["no usable evidence"]

    def eventFilter(self, obj, event):
        if obj is self.table.viewport() and event.type() == QEvent.Type.ToolTip:
            index = self.table.indexAt(event.pos())
            if index.isValid() and index.column() == 1:
                item = self.table.item(index.row(), 1)
                if item is not None:
                    entries = item.data(FONT_ENTRIES_ROLE)
                    if entries:
                        entry = self._entry_at_y(item, entries, event.pos().y())
                        if entry is None or entry["kind"] != "file":
                            QToolTip.hideText()
                            return True
                        QToolTip.showText(
                            event.globalPos(), self._file_entry_tooltip(entry)
                        )
                        return True
        return super().eventFilter(obj, event)

    def _entry_at_y(self, item, entries, y):
        font_metrics = QFontMetrics(item.font())
        top = self.table.visualItemRect(item).top()
        local_y = y - top
        if local_y < 0:
            return None
        width = max(self.table.columnWidth(1) - 14, 80)
        offset = 0
        for entry in entries:
            rect = font_metrics.boundingRect(
                QRect(0, 0, width, 1 << 30),
                Qt.TextWordWrap | Qt.AlignmentFlag.AlignLeft,
                entry["text"],
            )
            height = rect.height()
            if offset <= local_y < offset + height:
                return entry
            offset += height
        return None

    def _file_entry_tooltip(self, entry) -> str:
        lines = [entry["name"], "File: " + entry["file"]]
        if entry["repeats"] > 1:
            lines.append(f"Repeated {entry['repeats']} times (identical content)")
        lines.append("Family: " + entry["family"])
        return "\n".join(lines)

    def update_global_info(self, result):
        total_count = result["total_count"]
        total_size = get_readable_filesize(size_bytes=result["total_size"])
        unique_count = result["unique_count"]
        unique_size = get_readable_filesize(size_bytes=result["unique_size"])
        used_count = result["used_count"]
        used_size = get_readable_filesize(size_bytes=result["used_size"])
        text_items = []
        if total_count > 0:
            line = (
                "Attachments folder: "
                f"{total_count} files ({total_size}) -> "
                f"{unique_count} unique after dedupe ({unique_size})"
            )
            if used_count > 0:
                line += f" -> {used_count} fonts actually used ({used_size})"
            text_items.append(line)
        else:
            text_items.append("No attachments loaded.")
        if result["missing_custom"]:
            text_items.append(
                "Used but not attached (not standard system fonts): "
                + ", ".join(result["missing_custom"])
            )
        if result["missing_system"]:
            text_items.append(
                "Used standard system fonts (fallback): "
                + ", ".join(result["missing_system"])
            )
        self.global_info_label.setText("\n".join(text_items))

    def execute(self):
        self.exec()
