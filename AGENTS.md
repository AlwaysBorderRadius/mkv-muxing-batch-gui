# AGENTS.md — mkv muxing batch gui (fork)

GUI batch para muxear MKV con PySide6 + MKVToolNix. Entrada: `main.py`.
Lógica en `packages/`: `Startup/`, `Tabs/`, `Widgets/`.

## Stack

- **Python >=3.10**, **PySide6 >=6.9.2**, `psutil`, `comtypes` (win32), `fonttools>=4.54.0`.
- **MKVToolNix** vía `packages/Startup/GlobalFiles.py`: `MKVMERGE_PATH`, `MKVPROPEDIT_PATH`, `MKVEXTRACT_PATH` (sistema, Program Files o portable en `Resources/Tools/<sistema>/`).
- **Fuentes**: `packages/Tabs/AttachmentTab/FontAnalysis.py` (`TTFont`/`TTCollection`, `fontTools.subset`) + `packages/Tabs/AttachmentTab/Widgets/FontsAnalysisDialog.py` (preview por episodio en worker `QThread`).
- **Subtítulos**: `packages/Startup/SubtitleStartTimeSync.py` (parse SRT/ASS/SSA/VTT/SUB + sync por delay) + `packages/Tabs/SubtitleTab/Widgets/SubtitleStartReviewDialog.py` (overrides por archivo). Estado global en `packages/Tabs/GlobalSetting.py`, persistencia en `packages/Startup/Options.py` (`setting.json` en AppData).
- Sin tests automatizados: verificación = `ruff` + arranque smoke + prueba manual de mux con 1-2 episodios.

## Ficheros clave

- `packages/Tabs/AttachmentTab/FontAnalysis.py` — familias por hash, dedupe por identidad (PostScript), trim de glifos, extracción de embebidos (`extract_embedded_assets`).
- `packages/Tabs/AttachmentTab/Widgets/FontsAnalysisDialog.py` — `SeriesSummaryWorker` + tabla por grupo de subtítulos.
- `packages/Tabs/AttachmentTab/AttachmentSelection.py` — checkboxes `FilterUnused/FilterEmbedded/Trim` + `FontsAnalysisButton`.
- `packages/Startup/SubtitleStartTimeSync.py` — `get_subtitle_cues`, `compute_start_time_sync_delays`.
- `packages/Tabs/MuxSetting/Widgets/JobQueueTable.py` — `set_attachments_setting_for_job`, `apply_subtitle_start_time_sync`, `setup_queue`.
- `packages/Startup/Options.py`, `packages/Tabs/GlobalSetting.py` — flags nuevos `ATTACHMENT_FILTER_*`, `SUBTITLE_SET_AS_REFERENCE/SYNC_TO_REFERENCE/SYNC_START_OVERRIDES`.
- `Resources/Tools/Windows64/mkvextract.exe` — **excepción intencional**: se mantiene commiteado por decisión del dueño aunque sea binario pesado (~17 MB). No eliminarlo ni moverlo a LFS sin permiso explícito.

## Convenciones

- Python con type hints (`str | Path`, `tuple[...]`, `dict[...]`). `line-length = 90` (`ruff.toml` / `[tool.black]`).
- Cachés siempre con clave `(path, mtime, size)`, nunca solo `path` o solo `mtime`. Sin dicts globales sin cota: usar `lru_cache` o limpieza al cambiar de carpeta.
- `Path` vs `str`: `filter_and_trim_attachments` y `SingleJobData.attachments_absolute_path` deben mantener un solo tipo de extremo a extremo (`GetJsonForMkvmergeJob`, `MuxSetting.file_size`). No mezclar sin normalizar.
- Prohibido `except Exception: pass` silencioso en ruta de mux/extracción: advertir con `WarningDialog` o log. El fallback seguro es no filtrar, pero avisando.
- Trabajo pesado (`mkvmerge -J`, `mkvextract`, subset de fuentes) fuera del hilo GUI: `QThread`/`QThreadPool` con cancelación al cerrar el diálogo. No mantener locks durante subprocesos. Señales cross-thread con mutex/cola, nunca flag plano compartido.
- `QCheckBox`/`QPushButton` con tooltip deshabilitado: no duplicar `setEnabled/setDisabled/setToolTip` en cada widget, usar clase base común.
- `setdefault(key, f())` evalúa `f()` siempre: usar `if key not in d: d[key] = f()`.
- Comparar `Path` con `==`, nunca con `is`.
- Comentarios en inglés, cortos. Sin emojis en código.
- `.conf`/`.json` de AppData no se commitean; `Resources/Tools/*/mkvmerge|mkvpropedit` y `lib/` siguen ignorados (ver `.gitignore`). Solo `mkvextract.exe` Windows64 es excepción commiteada.

## Workflow (resumen; detalle en docs/workflow.md)

Ciclo por tarea: **plan → build → review**. Tras cada build: verificación + `/review` (subagente `reviewer`, read-only). Ramas: `main` estable, `dev` trabajo diario. Tras build verificado: commit + push a `dev` automático. A `main` solo por merge explícito + tag anotado `vN`.
