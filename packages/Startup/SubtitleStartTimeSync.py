import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from packages.Startup.Options import Options

TIME_SRT_START_RE = re.compile(r"^\s*(\d{1,3}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->")

TIME_VTT_FULL_START_RE = re.compile(r"^\s*(\d{1,3}):(\d{2}):(\d{2})[,.](\d{1,3})\s+-->")
TIME_VTT_SHORT_START_RE = re.compile(r"^\s*(\d{1,3}):(\d{2})[,.](\d{1,3})\s+-->")

TIME_ASS_FULL_RE = re.compile(
    r"^\s*Dialogue:\s*[^,]*,\s*(\d+):(\d{2}):(\d{2})[:.,](\d{1,3}),"
    r"[^,]*,\s*([^,]*),[^,]*,[^,]*,[^,]*,[^,]*,\s*([^,]*),(.*)$"
)

ASS_KARAOKE_TAG_RE = re.compile(r"\\[kK](?:[a-zA-Z])?\d")

MICRODVD_FPS_RE = re.compile(r"\A\{\d+\}\{\d+\}(\d+(?:\.\d+)?)\s*\Z")
MICRODVD_CUE_RE = re.compile(r"\A\{(\d+)\}\{(\d+)\}(.*)\Z")

ASS_OVERRIDE_TAGS_RE = re.compile(r"\{[^}]*\}")
ASS_LINE_BREAK_RE = re.compile(r"\\[nNhH]")
MULTI_SPACE_RE = re.compile(r"\s+")


@dataclass
class CueCandidate:
    start_ms: int
    text: str
    is_karaoke: bool = False
    end_ms: int | None = field(default=None)


def _time_to_ms(hours: int, minutes: int, seconds: int, fraction: str) -> int:
    fraction = str(fraction or "").strip() or "0"
    milliseconds = int(fraction.ljust(3, "0")[:3])
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds


def _decode_text(raw_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "utf-8", "cp1252"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("latin-1")


def _clean_text(text: str) -> str:
    text = text.strip()
    if text.startswith("{"):
        text = ASS_OVERRIDE_TAGS_RE.sub(" ", text)
    text = ASS_LINE_BREAK_RE.sub(" ", text)
    return MULTI_SPACE_RE.sub(" ", text).strip()


def _read_text(file_path: str | Path) -> str | None:
    path = Path(file_path)
    try:
        raw_bytes = path.read_bytes()
    except OSError:
        return None
    if not raw_bytes:
        return None
    return _decode_text(raw_bytes)


def _ass_karaoke_style_keywords() -> frozenset[str]:
    keywords = Options.Subtitle_Karaoke_Style_Keywords
    if not keywords:
        return frozenset()
    return frozenset(
        str(keyword).strip().lower() for keyword in keywords if str(keyword).strip()
    )


def _ass_karaoke_effect_keywords() -> frozenset[str]:
    keywords = Options.Subtitle_Karaoke_Effect_Keywords
    if not keywords:
        return frozenset()
    return frozenset(
        str(keyword).strip().lower() for keyword in keywords if str(keyword).strip()
    )


def _ass_is_karaoke(style: str, effect: str, text: str) -> bool:
    if Options.Subtitle_Karaoke_Tag_Filter and ASS_KARAOKE_TAG_RE.search(text):
        return True
    style_tokens = set(re.split(r"[^a-zA-Z0-9]+", style.lower()))
    if style_tokens & _ass_karaoke_style_keywords():
        return True
    effect_tokens = set(re.split(r"[^a-zA-Z0-9]+", effect.lower()))
    return bool(effect_tokens & _ass_karaoke_effect_keywords())


def _first_srt_start_ms(text: str) -> list[CueCandidate]:
    lines = text.splitlines()
    timestamp_lines = [i for i, line in enumerate(lines) if TIME_SRT_START_RE.match(line)]
    for cue_index, i in enumerate(timestamp_lines):
        match = TIME_SRT_START_RE.match(lines[i])
        hours, minutes, seconds = (int(match.group(i)) for i in (1, 2, 3))
        fraction = match.group(4)
        text_end = (
            timestamp_lines[cue_index + 1]
            if cue_index + 1 < len(timestamp_lines)
            else len(lines)
        )
        cue_lines = lines[i + 1 : text_end]
        while cue_lines and not cue_lines[0].strip():
            cue_lines = cue_lines[1:]
        if cue_lines and cue_lines[0].strip().isdigit():
            cue_lines = cue_lines[1:]
        cue_text = _clean_text(" ".join(cue_lines))
        if not cue_text:
            continue
        return [
            CueCandidate(
                start_ms=_time_to_ms(hours, minutes, seconds, fraction),
                text=cue_text,
            )
        ]
    return []


def _first_ass_start_ms(text: str) -> list[CueCandidate]:
    cues = []
    for line in text.splitlines():
        match = TIME_ASS_FULL_RE.match(line)
        if match:
            hours, minutes, seconds = (int(match.group(i)) for i in (1, 2, 3))
            fraction = match.group(4)
            style = match.group(5)
            effect = match.group(6)
            raw_text = match.group(7)
            is_karaoke = _ass_is_karaoke(style, effect, raw_text)
            cues.append(
                CueCandidate(
                    start_ms=_time_to_ms(hours, minutes, seconds, fraction),
                    text=_clean_text(raw_text),
                    is_karaoke=is_karaoke,
                )
            )
    cues.sort(key=lambda cue: cue.start_ms)
    return cues


def _first_vtt_start_ms(text: str) -> list[CueCandidate]:
    for i, line in enumerate(text.splitlines()):
        match = TIME_VTT_FULL_START_RE.match(line)
        if match:
            hours, minutes, seconds = (int(match.group(i)) for i in (1, 2, 3))
            fraction = match.group(4)
            cue_text = _clean_text(
                "\n".join(text.splitlines()[i + 1 :])
                .split("\n\n", 1)[0]
                .replace("\n", " ")
            )
            return [
                CueCandidate(
                    start_ms=_time_to_ms(hours, minutes, seconds, fraction),
                    text=cue_text,
                )
            ]
        match = TIME_VTT_SHORT_START_RE.match(line)
        if match:
            minutes, seconds = (int(match.group(i)) for i in (1, 2))
            fraction = match.group(3)
            cue_text = _clean_text(
                "\n".join(text.splitlines()[i + 1 :])
                .split("\n\n", 1)[0]
                .replace("\n", " ")
            )
            return [
                CueCandidate(
                    start_ms=_time_to_ms(0, minutes, seconds, fraction),
                    text=cue_text,
                )
            ]
    return []


def _first_microdvd_start_ms(text: str) -> list[CueCandidate]:
    fps = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if fps is None:
            fps_match = MICRODVD_FPS_RE.match(line)
            if fps_match:
                fps = float(fps_match.group(1))
                continue
        cue_match = MICRODVD_CUE_RE.match(line)
        if cue_match:
            start_frame = int(cue_match.group(1))
            if fps is None:
                fps = 25.0
            return [
                CueCandidate(
                    start_ms=round(start_frame / fps * 1000),
                    text=_clean_text(cue_match.group(3)),
                )
            ]
    return []


@cache
def get_subtitle_cues(file_path: str | Path) -> list[CueCandidate]:
    text = _read_text(file_path)
    if text is None:
        return []
    suffix = Path(file_path).suffix.lower()
    if suffix in (".srt", ".smi"):
        return _first_srt_start_ms(text)
    if suffix in (".ass", ".ssa"):
        return _first_ass_start_ms(text)
    if suffix in (".vtt",):
        return _first_vtt_start_ms(text)
    if suffix in (".sub",):
        return _first_microdvd_start_ms(text)
    return []


def invalidate_subtitle_cue_cache():
    get_subtitle_cues.cache_clear()


def get_subtitle_dialogue_start_cue(
    file_path: str | Path,
) -> tuple[CueCandidate | None, bool]:
    cues = get_subtitle_cues(file_path)
    if not cues:
        return None, False
    for cue in cues:
        if not cue.is_karaoke and cue.text.strip():
            return cue, False
    for cue in cues:
        if cue.text.strip():
            return cue, True
    return None, False


def get_first_subtitle_start_ms(file_path: str | Path) -> int | None:
    cue = get_subtitle_dialogue_start_cue(file_path)[0]
    return cue.start_ms if cue is not None else None


def compute_start_time_sync_delays(
    file_absolute_paths: list[str],
    current_delays_seconds: list[float],
    reference_position: int | None,
    sync_positions: list[int],
    start_time_overrides: dict[str, int] | None = None,
) -> tuple[list[float], list[str]]:
    new_delays = list(current_delays_seconds)
    warnings = []
    overrides = start_time_overrides or {}
    if reference_position is None or reference_position not in range(
        len(file_absolute_paths)
    ):
        return new_delays, warnings

    def effective_start_ms(path: str) -> tuple[int | None, bool]:
        if path in overrides:
            return overrides[path], False
        cue, is_fallback = get_subtitle_dialogue_start_cue(path)
        if cue is None:
            return None, False
        return cue.start_ms, is_fallback

    reference_start_ms, reference_is_fallback = effective_start_ms(
        file_absolute_paths[reference_position]
    )
    if reference_start_ms is None:
        reference_name = Path(file_absolute_paths[reference_position]).name
        warnings.append(
            'Reference subtitle "' + reference_name + '" is not supported or unreadable'
        )
        return new_delays, warnings
    if reference_is_fallback:
        reference_name = Path(file_absolute_paths[reference_position]).name
        warnings.append(
            'Subtitle "'
            + reference_name
            + '" looks like karaoke/sign lines, the earliest line was used as '
            "start-time, review it with the Review Start Lines button"
        )
    reference_delay_ms = round(float(current_delays_seconds[reference_position]) * 1000)
    target_start_ms = reference_start_ms + reference_delay_ms
    for position in sync_positions:
        if position == reference_position or position not in range(
            len(file_absolute_paths)
        ):
            continue
        this_start_ms, this_is_fallback = effective_start_ms(
            file_absolute_paths[position]
        )
        if this_start_ms is None:
            this_name = Path(file_absolute_paths[position]).name
            warnings.append(
                'Subtitle "'
                + this_name
                + '" is not supported or unreadable, it was not synchronized'
            )
            continue
        if this_is_fallback:
            this_name = Path(file_absolute_paths[position]).name
            warnings.append(
                'Subtitle "'
                + this_name
                + '" looks like karaoke/sign lines, the earliest line was used as '
                "start-time, review it with the Review Start Lines button"
            )
        new_delays[position] = round((target_start_ms - this_start_ms) / 1000.0, 5)
    return new_delays, warnings
