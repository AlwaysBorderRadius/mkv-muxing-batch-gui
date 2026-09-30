import os
from pathlib import Path

from PySide6.QtCore import QEvent, QRect, Qt, QSize, QThread, Signal
from PySide6.QtGui import QFontMetrics, QMovie
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
    QWidget,
)

from packages.Startup.GlobalFiles import SpinnerIconPath
from packages.Tabs.AttachmentTab import FontAnalysis
from packages.Tabs.GlobalSetting import GlobalSetting, get_readable_filesize
from packages.Widgets.MyDialog import MyDialog

WARNING_STYLE = (
    "background-color: #c62828; color: white; padding: 6px; border-radius: 4px;"
)
INFO_STYLE = "background-color: #1565C0; color: white; padding: 6px; border-radius: 4px;"

FONT_ENTRIES_ROLE = Qt.ItemDataRole.UserRole

_ACTIVE_ANALYSIS_WORKERS = set()


def _total_size(paths) -> int:
    total = 0
    for file_path in paths:
        try:
            total += os.path.getsize(file_path)
        except Exception:
            continue
    return total


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
    episode_signal = Signal(int, dict)
    finished_signal = Signal(dict)
    progress_signal = Signal(int)

    def __init__(self, attachment_paths, episode_labels, parent=None):
        super().__init__(parent)
        _ACTIVE_ANALYSIS_WORKERS.add(self)
        self.finished.connect(self._discard_from_registry)
        self.attachment_paths = list(attachment_paths)
        self.episode_labels = list(episode_labels)
        self._requested_episode = None

    def request_episode(self, episode_index):
        self._requested_episode = episode_index

    def _discard_from_registry(self):
        _ACTIVE_ANALYSIS_WORKERS.discard(self)

    def run(self):
        self._run_analysis()

    def _run_analysis(self):
        episode_count = get_episode_rows()
        used_families = set()
        family_display = {}
        embedded_fonts_all = []
        embedded_subs_all = []
        embedded_size = 0
        used_paths = set()
        order = list(range(episode_count))
        position = 0
        while position < len(order):
            requested = self._requested_episode
            self._requested_episode = None
            if requested is not None and requested in order[position:]:
                order.remove(requested)
                order.insert(position, requested)
            episode_index = order[position]
            position += 1
            video_path = None
            if episode_index < len(GlobalSetting.VIDEO_FILES_ABSOLUTE_PATH_LIST):
                video_path = GlobalSetting.VIDEO_FILES_ABSOLUTE_PATH_LIST[episode_index]
            self.progress_signal.emit(episode_index)
            embedded_fonts = []
            embedded_subs = []
            if GlobalSetting.ATTACHMENT_FILTER_EMBEDDED_FONTS and video_path:
                embedded_fonts, embedded_subs = FontAnalysis.extract_embedded_assets(
                    video_path
                )
            embedded_fonts = list(embedded_fonts)
            embedded_subs = list(embedded_subs)
            subtitle_groups = FontAnalysis.get_episode_subtitle_groups(episode_index)
            if embedded_subs:
                subtitle_groups = subtitle_groups + [
                    (-1, str(subtitle_path)) for subtitle_path in embedded_subs
                ]
            if GlobalSetting.ATTACHMENT_EXPERT_MODE:
                if len(GlobalSetting.ATTACHMENT_PATH_DATA_LIST) > episode_index:
                    source_paths = GlobalSetting.ATTACHMENT_PATH_DATA_LIST[
                        episode_index
                    ].files_list.copy()
                else:
                    source_paths = []
            else:
                source_paths = list(self.attachment_paths)
            if GlobalSetting.ATTACHMENT_FILTER_EMBEDDED_FONTS:
                embedded_fonts_all.extend(embedded_fonts)
                embedded_subs_all.extend(str(path) for path in embedded_subs)
                embedded_size += _total_size(embedded_fonts)
                source_paths = source_paths + [str(path) for path in embedded_fonts]
            if subtitle_groups:
                info = FontAnalysis.analyze_subtitle_groups(source_paths, subtitle_groups)
                for group in info["groups"]:
                    used_families.update(group["families"])
                    evidence = group["evidence"]
                    for family_key, family_evidence in evidence.items():
                        display = family_evidence.get("display")
                        if display:
                            family_display.setdefault(family_key, display)
            else:
                info = {
                    "groups": [],
                    "family_files": {},
                    "attachment_families": set(),
                    "missing_custom": [],
                    "missing_system": [],
                    "family_display": {},
                }
            total_size = get_readable_filesize(size_bytes=_total_size(source_paths))
            episode_label = (
                self.episode_labels[episode_index]
                if episode_index < len(self.episode_labels)
                else f"Episode {episode_index + 1}"
            )
            embedded_info = ""
            if GlobalSetting.ATTACHMENT_FILTER_EMBEDDED_FONTS:
                embedded_info = (
                    f" — {len(embedded_fonts)} font(s) and "
                    f"{len(embedded_subs)} subtitle track(s) embedded in this MKV"
                )
            subtitle_paths = [path for _, path in subtitle_groups]
            kept = FontAnalysis.filter_and_trim_attachments(
                source_paths, subtitle_paths, True, False
            )
            if GlobalSetting.ATTACHMENT_FILTER_UNUSED_FONTS:
                kept_size = get_readable_filesize(size_bytes=_total_size(kept))
                if GlobalSetting.ATTACHMENT_TRIM_UNUSED_GLYPHS:
                    final = FontAnalysis.filter_and_trim_attachments(
                        source_paths, subtitle_paths, True, True
                    )
                    final_size = get_readable_filesize(size_bytes=_total_size(final))
                    info_message = (
                        f"{episode_label} keeps {len(kept)} of {len(source_paths)} "
                        f"fonts ({kept_size} instead of {total_size})\n"
                        f"trimmed {len(final)} of {len(kept)} files "
                        f"({final_size} instead of {kept_size}){embedded_info}"
                    )
                else:
                    info_message = (
                        f"{episode_label} keeps {len(kept)} of {len(source_paths)} "
                        f"fonts ({kept_size} instead of {total_size}){embedded_info}"
                    )
            else:
                info_message = (
                    f"{episode_label}: the 'Attach Only Fonts Used by Subtitles' option "
                    "is off, so all attached fonts would be muxed "
                    f"({len(source_paths)} files, {total_size}).{embedded_info}"
                )
            if subtitle_groups:
                used_paths.update(str(path) for path in kept)
            banner_text = ""
            banner_style = None
            if info["missing_custom"]:
                banner_text = (
                    "Fonts used by these subtitles but not attached, and not "
                    "standard system fonts:\n"
                    + ", ".join(
                        info["family_display"].get(family, family)
                        for family in info["missing_custom"]
                    )
                )
                banner_style = WARNING_STYLE
            elif info["missing_system"]:
                banner_text = (
                    "Standard system fonts used (not attached; the player will use "
                    "its local fallback):\n"
                    + ", ".join(
                        info["family_display"].get(family, family)
                        for family in info["missing_system"]
                    )
                )
                banner_style = INFO_STYLE
            self.episode_signal.emit(
                episode_index,
                {
                    "info": info,
                    "info_message": info_message,
                    "banner_text": banner_text,
                    "banner_style": banner_style,
                },
            )
        existing_paths = [
            Path(file_path)
            for file_path in self.attachment_paths
            if file_path and os.path.isfile(file_path)
        ] + list(embedded_fonts_all)
        attachment_families = FontAnalysis.get_families_in_attachments(existing_paths)
        missing = set(used_families) - attachment_families
        missing_custom = sorted(
            family for family in missing if not FontAnalysis.is_common_system_font(family)
        )
        missing_system = sorted(
            family for family in missing if FontAnalysis.is_common_system_font(family)
        )
        unique_paths = FontAnalysis.dedupe_attachments(existing_paths)
        result = {
            "families": sorted(used_families),
            "missing_custom": [
                family_display.get(family, family) for family in missing_custom
            ],
            "missing_system": [
                family_display.get(family, family) for family in missing_system
            ],
            "total_count": len(existing_paths),
            "total_size": _total_size(existing_paths),
            "unique_count": len(unique_paths),
            "unique_size": _total_size(unique_paths),
            "used_count": len(used_paths),
            "used_size": _total_size(used_paths),
            "embedded_font_count": len(embedded_fonts_all),
            "embedded_size": embedded_size,
            "embedded_sub_count": len(embedded_subs_all),
        }
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

        self._closed = False
        self._episode_cache = {}
        self.load_icon_movie = QMovie(str(SpinnerIconPath))
        self.load_icon_movie.setScaledSize(QSize(22, 22))
        self.load_icon_movie.setSpeed(120)
        self.load_icon_label = QLabel()
        self.load_icon_label.setMovie(self.load_icon_movie)
        self.loading_text_label = QLabel("")
        self.loading_layout = QHBoxLayout()
        self.loading_layout.setContentsMargins(0, 0, 0, 0)
        self.loading_layout.setSpacing(8)
        self.loading_layout.addWidget(self.load_icon_label)
        self.loading_layout.addWidget(self.loading_text_label)
        self.loading_layout.addStretch(1)
        self.loading_widget = QWidget()
        self.loading_widget.setLayout(self.loading_layout)
        self.loading_widget.hide()

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
        self.table.setWordWrap(True)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.verticalScrollBar().setSingleStep(
            QFontMetrics(self.table.font()).lineSpacing()
        )
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
        self.main_layout.addWidget(self.loading_widget)
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

        episode_labels = []
        for i in range(self.episode_count):
            if i < len(GlobalSetting.VIDEO_FILES_LIST):
                episode_labels.append(Path(GlobalSetting.VIDEO_FILES_LIST[i]).name)
            else:
                episode_labels.append(f"Episode {i + 1} (no video)")

        if self.episode_count > 0:
            self.episode_combo.addItems(episode_labels)
            self.episode_combo.setCurrentIndex(0)
            self.global_info_label.setText("Analyzing episodes and embedded fonts…")
        else:
            self.episode_combo.setEnabled(False)
            self.global_info_label.setText(
                "No videos or subtitles loaded. Open the Video/Subtitle/Groups "
                "tabs to see the per-episode font breakdown."
            )

        self.worker = SeriesSummaryWorker(get_all_attachment_paths(), episode_labels)
        self.worker.progress_signal.connect(self.update_loading_progress)
        self.worker.episode_signal.connect(self.handle_episode_result)
        self.worker.finished_signal.connect(self.update_global_info)
        self.worker.finished_signal.connect(self._global_analysis_done)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _set_loading_visible(self, visible):
        self.loading_widget.setVisible(visible)
        if visible:
            self.load_icon_movie.start()
        else:
            self.load_icon_movie.stop()

    def update_loading_progress(self, episode_index):
        if self._closed:
            return
        self.loading_text_label.setText(
            f"Analyzing episode {episode_index + 1}/{self.episode_count}…"
        )

    def handle_episode_result(self, episode_index, result):
        if self._closed:
            return
        self._episode_cache[episode_index] = result
        if self.episode_combo.currentIndex() == episode_index:
            self._render_episode_result(result)

    def _global_analysis_done(self, _result):
        if self._closed:
            return
        self._set_loading_visible(False)

    def _render_episode_result(self, result):
        self.banner_label.hide()
        self.table.clearContents()
        self.update_fonts_table(result["info"])
        self.episode_info_label.setText(result["info_message"])
        if result.get("banner_text"):
            self.banner_label.setStyleSheet(result.get("banner_style") or INFO_STYLE)
            self.banner_label.setText(result["banner_text"])
            self.banner_label.show()
        self._set_loading_visible(False)

    def refresh_episode(self, *_):
        self.banner_label.hide()
        self.table.clearContents()
        episode_index = self.episode_combo.currentIndex()
        if self.episode_count == 0 or episode_index < 0:
            self.episode_info_label.setText("")
            return
        cached = self._episode_cache.get(episode_index)
        if cached is not None:
            self._render_episode_result(cached)
        else:
            self.episode_info_label.setText("")
            self._set_loading_visible(True)
            worker = getattr(self, "worker", None)
            if worker is not None:
                worker.request_episode(episode_index)

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
                family_display = info["family_display"]
                for family in sorted(families):
                    evidence = group["evidence"].get(family, {})
                    display = family_display.get(family, family)
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
                        family_lines.append(mark + "  " + display)
                        entries.append(
                            {
                                "kind": "family",
                                "status": "missing_custom",
                                "text": "✗  " + display,
                                "family": family,
                            }
                        )
                    else:
                        mark = "⚠"
                        family_lines.append(mark + "  " + display)
                        entries.append(
                            {
                                "kind": "family",
                                "status": "missing_system",
                                "text": "⚠  " + display,
                                "family": family,
                            }
                        )
                    mechanisms = self._evidence_mechanisms(evidence)
                    if mechanisms:
                        evidence_lines.append(f"[{display}]")
                        evidence_lines.extend(m for m in mechanisms)
                        evidence_lines.append("")
                fonts_text = "\n".join(family_lines)
                evidence_text = "\n".join(evidence_lines).strip()
                if evidence_text == "":
                    evidence_text = "—"
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
        self.table.resizeRowsToContents()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        table = getattr(self, "table", None)
        if table is not None and table.rowCount() > 0:
            self.table.resizeRowsToContents()

    def showEvent(self, event):
        super().showEvent(event)
        table = getattr(self, "table", None)
        if table is not None and table.rowCount() > 0:
            self.table.resizeRowsToContents()

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
                        if entry is None:
                            QToolTip.hideText()
                            return True
                        if entry["kind"] == "file":
                            QToolTip.showText(
                                event.globalPos(), self._file_entry_tooltip(entry)
                            )
                        elif entry["kind"] == "family":
                            QToolTip.showText(
                                event.globalPos(), self._family_entry_tooltip(entry)
                            )
                        return True
        return super().eventFilter(obj, event)

    def _entry_at_y(self, item, entries, y):
        font_metrics = QFontMetrics(item.font())
        top = self.table.visualItemRect(item).top()
        local_y = y - top
        if local_y < 0:
            return None
        width = max(self.table.columnWidth(1) - 6, 80)
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

    def _family_entry_tooltip(self, entry) -> str:
        family = entry["family"]
        if entry["status"] == "missing_custom":
            return (
                f"Family '{family}' is used by the subtitles but no matching font "
                "file is attached.\n\n"
                "Add this font (plus any bold/italic variants the styled subtitles "
                "may use) so the subtitles render as intended."
            )
        return (
            f"Family '{family}' is used by the subtitles but no matching font file "
            "is attached.\n\n"
            "You may already have it installed in your operating system, "
            "so the subtitles will fall back to it."
        )

    def update_global_info(self, result):
        if self._closed:
            return
        total_count = result["total_count"]
        total_size = get_readable_filesize(size_bytes=result["total_size"])
        unique_count = result["unique_count"]
        unique_size = get_readable_filesize(size_bytes=result["unique_size"])
        used_count = result["used_count"]
        used_size = get_readable_filesize(size_bytes=result["used_size"])
        embedded_font_count = result.get("embedded_font_count", 0)
        embedded_size = get_readable_filesize(size_bytes=result.get("embedded_size", 0))
        embedded_sub_count = result.get("embedded_sub_count", 0)
        video_count = len(GlobalSetting.VIDEO_FILES_ABSOLUTE_PATH_LIST)
        text_items = []
        if embedded_font_count > 0:
            external_count = total_count - embedded_font_count
            line = f"{video_count} videos: {embedded_font_count} font(s) embedded in the MKVs ({embedded_size})"
            if external_count > 0:
                line += f" + {external_count} external attachment(s)"
            line += f" -> {unique_count} unique after dedupe ({unique_size})"
            if used_count > 0:
                line += f" -> {used_count} fonts actually used ({used_size})"
            text_items.append(line)
            if embedded_sub_count > 0:
                text_items.append(
                    f"{embedded_sub_count} ASS/SSA subtitle track(s) found embedded in the videos"
                )
        elif total_count > 0:
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

    def closeEvent(self, event):
        self._closed = True
        self.load_icon_movie.stop()
        try:
            self.worker.progress_signal.disconnect()
            self.worker.episode_signal.disconnect()
            self.worker.finished_signal.disconnect()
        except (RuntimeError, TypeError):
            pass
        super().closeEvent(event)

    def execute(self):
        self.exec()
