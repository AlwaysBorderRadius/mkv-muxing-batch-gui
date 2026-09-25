import hashlib
import io
import os
import re
import time
from collections import defaultdict
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.ttLib.ttCollection import TTCollection

from packages.Startup.GlobalFiles import TrimmedFontsFolderPath
from packages.Tabs.GlobalSetting import GlobalSetting

FONT_EXTENSIONS = {".ttf", ".otf", ".ttc", ".otc"}

COMMON_SYSTEM_FONT_FAMILIES = frozenset(
    name.casefold()
    for name in (
        "Arial",
        "Arial Black",
        "Arial Narrow",
        "Helvetica",
        "Helvetica Neue",
        "Times New Roman",
        "Times",
        "Courier New",
        "Courier",
        "Lucida Console",
        "Lucida Sans Unicode",
        "Calibri",
        "Cambria",
        "Candara",
        "Consolas",
        "Constantia",
        "Corbel",
        "Segoe UI",
        "Segoe Script",
        "Tahoma",
        "Verdana",
        "Georgia",
        "Trebuchet MS",
        "Impact",
        "Comic Sans MS",
        "Gill Sans",
        "Futura",
        "Palatino",
        "Garamond",
        "Book Antiqua",
        "Franklin Gothic",
        "MS Gothic",
        "MS PGothic",
        "MS UI Gothic",
        " Yu Gothic",
        "Yu Mincho",
        "Meiryo",
        "Hiragino Kaku Gothic",
        "Hiragino Mincho Pro",
        " Osaka",
        "Osaka-Mono",
        "Kyokasho",
        "Noto Sans",
        "Noto Serif",
        "Noto Sans CJK",
        "Noto Serif CJK",
        "Noto Sans JP",
        "Noto Serif JP",
        "Liberation Sans",
        "Liberation Serif",
        "Liberation Mono",
        "DejaVu Sans",
        "DejaVu Serif",
        "DejaVu Sans Mono",
        "Ubuntu",
        "Roboto",
        "Open Sans",
        "Lato",
        "Cantarell",
        "FreeSans",
        "FreeSerif",
        "FreeMono",
        "Symbol",
        "Wingdings",
        "Webdings",
        "Marlett",
    )
)
BASE_CHARS = (
    "\n\r\t "
    + "0123456789"
    + "abcdefghijklmnopqrstuvwxyz"
    + "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    + ".,:;!?()[]{}'\"-/\\|&%$#@*+=^~`<>_"
    + "\u00a0\u3000\ufffd\u2018\u2019\u201c\u201d"
)
_LATIN_KEEP_RANGES = (
    (0x20, 0x7E),
    (0xA0, 0xFF),
    (0x100, 0x17F),
    (0x180, 0x24F),
    (0x1E00, 0x1EFF),
)
_FULL_LATIN_KEEP = frozenset(
    codepoint for low, high in _LATIN_KEEP_RANGES for codepoint in range(low, high + 1)
)
TRIM_CACHE_MAX_AGE_DAYS = 2

_STYLE_SECTION_RE = re.compile(r"^\s*\[(v3|v4|v4\+)\s+styles\]\s*$", re.IGNORECASE)
_EVENTS_SECTION_RE = re.compile(r"^\s*\[events\]\s*$", re.IGNORECASE)

# content hash -> set of normalized family names
_family_cache = {}
# (content hash, chars key) -> trimmed file path
_trim_cache = {}
# absolute path -> (mtime, size, content hash)
_stat_cache = {}
# absolute path -> (mtime, used families, used codepoints, evidence)
_subtitle_usage_cache = {}
# content hash -> True if the file name table contains "strp"
_strp_cache = {}
# content hash -> (identity key, display name, glyph count)
_identity_cache = {}
_trim_cache_loaded = False
_cleanup_done = False


def _cleanup_old_trimmed_fonts():
    global _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True
    cleanup_old_trimmed_fonts()


def normalize_family_name(name) -> str:
    return str(name).replace("@", "", 1).strip().casefold()


def get_content_hash(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _get_font_data(path) -> bytes | None:
    try:
        stat = os.stat(path)
        cache_key = str(path)
        cached = _stat_cache.get(cache_key)
        if (
            cached is not None
            and cached[0] == stat.st_mtime
            and cached[1] == stat.st_size
        ):
            return None, cached[2], None
        data = Path(path).read_bytes()
        content_hash = get_content_hash(data)
        _stat_cache[cache_key] = (stat.st_mtime, stat.st_size, content_hash)
        return data, content_hash, None
    except Exception:
        return None, None, None


def _get_families_from_ttfont(font: TTFont) -> set[str]:
    families = set()
    try:
        for record in font["name"].names:
            if record.nameID in (1, 16):
                try:
                    value = record.toUnicode()
                except Exception:
                    continue
                if value:
                    families.add(normalize_family_name(value))
    except Exception:
        pass
    return families


def _font_name_has_strp(path) -> bool:
    """Return True when any internal name record contains "strp" (a pre-stripped
    font marker added by some download tools)."""
    data, _, _ = _get_font_data(path)
    if data is None:
        try:
            data = Path(path).read_bytes()
        except Exception:
            return False
    try:
        font = TTFont(io.BytesIO(data), lazy=True)
        for record in font["name"].names:
            try:
                if "strp" in record.toUnicode().casefold():
                    return True
            except Exception:
                continue
    except Exception:
        return False
    return False


def _families_from_font_data(data: bytes) -> set[str]:
    families = set()
    try:
        if len(data) >= 4 and data[:4] == b"ttcf":
            collection = TTCollection(io.BytesIO(data), lazy=True)
            for font in collection.fonts:
                families.update(_get_families_from_ttfont(font))
        else:
            font = TTFont(io.BytesIO(data), lazy=True)
            families.update(_get_families_from_ttfont(font))
    except Exception:
        pass
    return families


def analyze_font_file(path) -> tuple[str | None, set[str]]:
    """Return (content hash, normalized families) reading the file at most once
    per (path, mtime, size)."""
    stat_tuple = _get_font_data(path)
    data, content_hash, cached_from_stat = stat_tuple
    if data is None:
        if content_hash is None:
            return None, set()
        # stat cache hit: families already cached for this content hash
        if content_hash in _family_cache:
            return content_hash, _family_cache[content_hash]
        try:
            data = Path(path).read_bytes()
        except Exception:
            return content_hash, _family_cache.get(content_hash, set())
    if content_hash in _family_cache:
        return content_hash, _family_cache[content_hash]
    families = _families_from_font_data(data)
    _family_cache[content_hash] = families
    return content_hash, families


def get_families_from_font_file(path) -> set[str]:
    _, families = analyze_font_file(path)
    return families


def _get_name_record(font: TTFont, name_id: int) -> str | None:
    try:
        for record in font["name"].names:
            if record.nameID == name_id:
                value = record.toUnicode()
                if value:
                    return value
    except Exception:
        pass
    return None


def _identity_from_font_data(data: bytes) -> tuple[str | None, str | None, int]:
    """Return (identity key, display name, glyph count) for font bytes. The key is a
    clean PostScript name (nameID 6) when available so that distinct binaries of the
    same logical font collapse; falling back to family+style. The display name is the
    human-friendly version shown in the analysis; glyphs picks the most complete file."""
    try:
        if len(data) >= 4 and data[:4] == b"ttcf":
            fonts = TTCollection(io.BytesIO(data), lazy=True).fonts
        else:
            fonts = [TTFont(io.BytesIO(data), lazy=True)]
    except Exception:
        return None, None, 0
    best = None
    for font in fonts:
        glyphs = 0
        try:
            glyphs = font["maxp"].numGlyphs
        except Exception:
            continue
        if best is None or glyphs > best[1]:
            best = (font, glyphs)
    if best is None:
        return None, None, 0
    font, glyphs = best
    psname = _get_name_record(font, 6)
    family = _get_name_record(font, 1) or _get_name_record(font, 16)
    style = _get_name_record(font, 2) or _get_name_record(font, 17)
    if psname:
        return psname.casefold(), psname, glyphs
    if family:
        return (
            normalize_family_name(family)
            + "|"
            + normalize_family_name(style or "regular"),
            (family + " " + style).strip() or family,
            glyphs,
        )
    return None, None, glyphs


def get_font_identity(path) -> tuple[str | None, str, int]:
    """Return (identity key, display name, glyph count) for a font file, cached per
    content hash. The key collapses distinct binaries of the same logical font so the
    mux/analysis can keep only the most complete copy."""
    stat_tuple = _get_font_data(path)
    data, content_hash, _ = stat_tuple
    if data is None:
        if content_hash is None:
            return None, str(Path(path).stem), 0
        if content_hash in _identity_cache:
            return _identity_cache[content_hash]
        try:
            data = Path(path).read_bytes()
        except Exception:
            return _identity_cache.get(content_hash, (None, str(Path(path).stem), 0))
    if content_hash in _identity_cache:
        return _identity_cache[content_hash]
    key, display, glyphs = _identity_from_font_data(data)
    if key is None:
        key = "hash:" + content_hash
        if display is None:
            display = str(Path(path).stem)
    identity = (key, display, glyphs)
    if content_hash is not None:
        _identity_cache[content_hash] = identity
    return identity


def is_font_file(path) -> bool:
    return Path(path).suffix.lower() in FONT_EXTENSIONS


def get_fonts_used_by_subtitle_files(subtitle_paths) -> tuple[set[str], set[int]]:
    """Return (normalized used families, used codepoints) for the subtitle files.

    A family is used when it belongs to a style referenced by at least one event
    (the event Style field or a {\\rName} reset) or when it appears in a {\\fn...}
    override. If a file has no parseable events, all of its styles count as used.
    Non ASS/SSA files are ignored; if no ASS/SSA file exists at all, an empty
    result is returned (meaning: do not filter)."""
    used_families = set()
    used_chars = set()
    found_ass = False
    for subtitle_path in subtitle_paths:
        if not subtitle_path:
            continue
        path = Path(subtitle_path)
        if path.suffix.lower() not in (".ass", ".ssa"):
            continue
        found_ass = True
        try:
            families, chars, _ = get_subtitle_font_usage(path)
        except Exception:
            families, chars = set(), set()
        used_families.update(families)
        used_chars.update(chars)
    if not found_ass:
        return set(), set()
    return used_families, used_chars


def _read_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le"):
        try:
            return raw.decode(encoding)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def _parse_subtitle_file(path: Path) -> tuple[set[str], set[int], dict]:
    text = _read_text_file(path)
    styles = {}  # style name (raw) -> normalized font name
    used_families = set()
    used_chars = set()
    style_referenced = set()
    in_styles = False
    in_events = False
    style_format: list[str] = []
    event_format: list[str] = []
    events_count = 0
    tag_re = re.compile(r"\{([^{}]*)\}")
    family_style_lines: dict[str, dict[str, int]] = defaultdict(dict)
    family_fn_count: dict[str, int] = defaultdict(int)
    family_reset_count: dict[str, dict[str, int]] = defaultdict(dict)
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("["):
            in_styles = bool(_STYLE_SECTION_RE.match(line))
            in_events = bool(_EVENTS_SECTION_RE.match(line))
            continue
        if in_styles:
            if stripped.startswith("Format:"):
                style_format = [item.strip() for item in stripped[7:].split(",")]
            elif stripped.startswith("Style:"):
                parts = stripped[6:].split(",")
                if len(parts) < 2:
                    continue
                style_name = parts[0].strip()
                font_index = 1
                if style_format and "Fontname" in style_format:
                    font_index = style_format.index("Fontname")
                if font_index >= len(parts):
                    continue
                styles[style_name] = normalize_family_name(parts[font_index])
            continue
        if in_events:
            if stripped.startswith("Format:"):
                event_format = [item.strip() for item in stripped[7:].split(",")]
                continue
            if not (stripped.startswith("Dialogue:") or stripped.startswith("Comment:")):
                continue
            is_dialogue = stripped.startswith("Dialogue:")
            events_count += 1
            fields = stripped.split(",")
            if len(fields) < 9:
                continue
            style_index = 3
            text_index = 9
            if event_format:
                style_index = (
                    event_format.index("Style") if "Style" in event_format else 3
                )
                text_index = len(event_format) - 1
            if style_index >= len(fields):
                continue
            style_name = fields[style_index].strip()
            if style_name:
                style_referenced.add(style_name)
            text_content = ",".join(fields[text_index:])
            line_families = set()
            if style_name and style_name in styles:
                line_families.add(styles[style_name])
            tags = tag_re.findall(text_content)
            for tag in tags:
                for element in tag.split("\\"):
                    if element.startswith("fn"):
                        family_name = element[2:].strip()
                        if family_name and family_name not in ("0", "0.0"):
                            normalized = normalize_family_name(family_name)
                            used_families.add(normalized)
                            family_fn_count[normalized] += 1
                            line_families.add(normalized)
                    elif element.startswith("r") and len(element) > 1:
                        reset_name = element[1:].strip()
                        if reset_name:
                            style_referenced.add(reset_name)
                            if reset_name in styles:
                                family = styles[reset_name]
                                line_families.add(family)
                                if is_dialogue:
                                    reset_counts = family_reset_count[family]
                                    reset_counts[reset_name] = (
                                        reset_counts.get(reset_name, 0) + 1
                                    )
            visible_text = tag_re.sub("", text_content)
            for character in visible_text:
                used_chars.add(ord(character))
            if is_dialogue:
                if style_name and style_name in styles:
                    family = styles[style_name]
                    style_counts = family_style_lines[family]
                    style_counts[style_name] = style_counts.get(style_name, 0) + 1
    for style_name, font_name in styles.items():
        if not font_name:
            continue
        if style_name in style_referenced:
            used_families.add(font_name)
    fallback_used = not used_families and styles and events_count == 0
    if fallback_used:
        for style_name, font_name in styles.items():
            if font_name:
                used_families.add(font_name)
    evidence = {}
    for family in used_families:
        style_counts = family_style_lines.get(family)
        reset_counts = family_reset_count.get(family)
        evidence[family] = {
            "styles": dict(style_counts) if style_counts else None,
            "fn_count": family_fn_count.get(family, 0),
            "resets": dict(reset_counts) if reset_counts else None,
            "fallback": fallback_used,
        }
    return used_families, used_chars, evidence


def get_subtitle_font_usage(path) -> tuple[set[str], set[int], dict]:
    """Return (used families, used codepoints, per-family evidence), caching the
    result per (path, mtime) so repeated calls across tabs/dialogs are cheap."""
    cache_key = str(path)
    try:
        stat = os.stat(path)
    except Exception:
        stat = None
    cached = _subtitle_usage_cache.get(cache_key)
    if cached is not None and stat is not None:
        if cached[0] == stat.st_mtime and cached[1] == stat.st_size:
            return cached[2], cached[3], cached[4]
    try:
        families, chars, evidence = _parse_subtitle_file(Path(path))
    except Exception:
        return set(), set(), {}
    if stat is not None:
        _subtitle_usage_cache[cache_key] = (
            stat.st_mtime,
            stat.st_size,
            families,
            chars,
            evidence,
        )
    return families, chars, evidence


def get_families_in_attachments(attachment_paths) -> set[str]:
    """Union of normalized family names across all font files in the attachment
    list (uses the shared content-hash family cache)."""
    families = set()
    for attachment_path in attachment_paths:
        if not attachment_path:
            continue
        path = Path(attachment_path)
        if not is_font_file(path):
            continue
        _, file_families = analyze_font_file(path)
        families.update(file_families)
    return families


def get_episode_subtitle_groups(row_id: int) -> list[tuple[int, str]]:
    """Subtitle groups (tab_index, absolute path) present in the given episode row
    across all subtitle tabs. Shared by the mux pipeline and the analysis dialog so
    the preview always matches what the mux will do."""
    groups = []
    for (
        tab_index,
        subtitle_list,
    ) in GlobalSetting.SUBTITLE_FILES_ABSOLUTE_PATH_LIST.items():
        if len(subtitle_list) > row_id and subtitle_list[row_id]:
            groups.append((tab_index, str(subtitle_list[row_id])))
    return groups


def get_episode_subtitle_paths(row_id: int) -> list[str]:
    return [path for _, path in get_episode_subtitle_groups(row_id)]


def is_common_system_font(family_name) -> bool:
    return normalize_family_name(family_name) in COMMON_SYSTEM_FONT_FAMILIES


def analyze_subtitle_groups(attachment_paths, subtitle_groups) -> dict:
    """Build the per-group analysis shown by the Fonts Analysis dialog: families,
    evidence and status of each used family vs. the attached fonts."""
    hash_groups: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    content_paths: dict[str, Path] = {}
    for attachment_path in attachment_paths:
        if not attachment_path:
            continue
        path = Path(attachment_path)
        if not is_font_file(path):
            continue
        content_hash, file_families = analyze_font_file(path)
        hash_key = content_hash or f"none:{path.name}"
        if content_hash is not None:
            content_paths.setdefault(content_hash, path)
        for family in file_families:
            hash_groups[family][hash_key].append(path.name)
    family_files: dict[str, list[dict]] = {}
    for family, by_hash in hash_groups.items():
        identities = {
            content_hash: (
                get_font_identity(content_paths.get(content_hash))
                if content_hash in content_paths
                else (None, None, 0)
            )
            for content_hash in by_hash
        }
        buckets: dict[str, list[str]] = {}
        for content_hash in by_hash:
            key = identities[content_hash][0] or content_hash
            buckets.setdefault(key, []).append(content_hash)
        items = []
        for group in buckets.values():
            winner = max(
                group,
                key=lambda content_hash: (
                    identities[content_hash][2],
                    sorted(by_hash[content_hash])[0],
                ),
            )
            _, display, _ = identities[winner]
            names = by_hash[winner]
            first_name = sorted(names)[0]
            items.append(
                {
                    "file": first_name,
                    "display": display or first_name,
                    "repeats": len(names),
                }
            )
        family_files[family] = sorted(items, key=lambda item: item["file"])
    attachment_families = set(family_files)
    groups = []
    used_union = set()
    for tab_index, path in subtitle_groups:
        families, chars, evidence = get_subtitle_font_usage(path)
        used_union.update(families)
        groups.append(
            {
                "tab_index": tab_index,
                "path": str(path),
                "families": families,
                "chars": chars,
                "evidence": evidence,
            }
        )
    missing = sorted(
        (family for family in used_union if family not in attachment_families)
    )
    missing_custom = sorted(
        (family for family in missing if not is_common_system_font(family))
    )
    missing_system = sorted(
        (family for family in missing if is_common_system_font(family))
    )
    return {
        "groups": groups,
        "used_union": used_union,
        "attachment_families": attachment_families,
        "family_files": family_files,
        "missing_custom": missing_custom,
        "missing_system": missing_system,
    }


def dedupe_attachments(files) -> list[Path]:
    """Keep one representative per identical font content and one per logical font
    (same PostScript name / family+style), preferring the most complete copy (most
    glyphs). Shared by the mux filter and the analysis preview so they always match.
    Non font files are kept."""
    seen_hash = set()
    result = []
    for file_path in files:
        path = Path(file_path)
        if not is_font_file(path):
            result.append(path)
            continue
        content_hash, _ = analyze_font_file(path)
        if content_hash is None:
            result.append(path)
            continue
        if content_hash in seen_hash:
            continue
        seen_hash.add(content_hash)
        result.append(path)
    if len(result) < 2:
        return result
    candidates: dict[str, tuple[Path, int]] = {}
    identity: dict[Path, tuple[str | None, int]] = {}
    for path in result:
        _, key, glyphs = get_font_identity(path)
        identity[path] = (key, glyphs)
        if key is None:
            continue
        previous = candidates.get(key)
        if previous is None or glyphs > previous[1]:
            candidates[key] = (path, glyphs)
    final = []
    for path in result:
        key, _ = identity.get(path, (None, 0))
        if key is not None and key in candidates:
            if candidates[key][0] is not path:
                continue
        final.append(path)
    return final


def _trim_output_dir(content_hash: str, chars_key: str) -> Path:
    return TrimmedFontsFolderPath / f"{content_hash}_{chars_key}"


def _load_trim_cache():
    global _trim_cache_loaded
    if _trim_cache_loaded:
        return
    _trim_cache_loaded = True
    try:
        for folder in TrimmedFontsFolderPath.iterdir():
            if not folder.is_dir():
                continue
            try:
                content_hash, chars_key = folder.name.rsplit("_", 1)
            except ValueError:
                continue
            if len(content_hash) != 40:
                continue
            for file_path in folder.iterdir():
                if file_path.is_file():
                    _trim_cache[(content_hash, chars_key)] = file_path
                    break
    except Exception:
        pass


def trim_font_file(path, chars: set[int]) -> Path:
    """Return a subsetted font (with the original base name) that renders the given
    characters. Falls back to the original file on any failure or if the result
    would not be smaller."""
    p = Path(path)
    if "strp" in p.name.casefold():
        return p
    content_hash, _ = analyze_font_file(path)
    if content_hash is None:
        return p
    if _strp_cache.setdefault(content_hash, _font_name_has_strp(path)):
        return p
    if p.suffix.lower() in (".ttc", ".otc"):
        return p
    keep_chars = chars | _FULL_LATIN_KEEP
    chars_key = hashlib.sha1(
        "".join(chr(codepoint) for codepoint in sorted(keep_chars)).encode("utf-8")
    ).hexdigest()[:16]
    _load_trim_cache()
    cache_key = (content_hash, chars_key)
    if cache_key in _trim_cache:
        cached_path = _trim_cache[cache_key]
        if cached_path.exists() and cached_path.stat().st_size > 0:
            return cached_path
    output_folder = _trim_output_dir(content_hash, chars_key)
    output_path = output_folder / Path(path).name
    try:
        data = Path(path).read_bytes()
        font = TTFont(io.BytesIO(data), lazy=True)
        if "fvar" in font:
            return Path(path)
        options = subset.Options()
        options.name_IDs = [0, 1, 2, 3, 4, 5, 6]
        options.name_languages = ["*"]
        options.layout_features = ["*"]
        options.ignore_missing_unicodes = True
        options.notdef_glyph = True
        options.notdef_outline = True
        text = BASE_CHARS + "".join(chr(codepoint) for codepoint in sorted(keep_chars))
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(text=text)
        subsetter.subset(font)
        output_folder.mkdir(parents=True, exist_ok=True)
        subset.save_font(font, str(output_path), options)
        if output_path.stat().st_size >= Path(path).stat().st_size:
            output_path.unlink(missing_ok=True)
            return Path(path)
        _trim_cache[cache_key] = output_path
        return output_path
    except Exception:
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        return Path(path)


def filter_and_trim_attachments(
    attachment_paths,
    subtitle_paths,
    filter_unused_fonts: bool,
    trim_glyphs: bool,
):
    """Hito 1 for one job row: dedupe identical fonts, keep only used families and
    optionally trim each kept font to the characters the subtitles really use.
    Trimming only applies when filtering by used families is also active."""
    if trim_glyphs and not filter_unused_fonts:
        trim_glyphs = False
    attachments = [Path(path) for path in attachment_paths]
    if not attachments or not (filter_unused_fonts or trim_glyphs):
        return attachments
    _cleanup_old_trimmed_fonts()
    used_families, used_chars = get_fonts_used_by_subtitle_files(subtitle_paths)
    if not used_families:
        return attachments
    files = dedupe_attachments(attachments)
    if filter_unused_fonts:
        selected = []
        for file_path in files:
            if not is_font_file(file_path):
                selected.append(file_path)
                continue
            _, families = analyze_font_file(file_path)
            if not families:
                selected.append(file_path)
                continue
            if families & used_families:
                selected.append(file_path)
        files = selected
    if trim_glyphs:
        files = [trim_font_file(file_path, used_chars) for file_path in files]
    return files


def cleanup_old_trimmed_fonts():
    """Delete trimmed font files older than a few days (they are cheap to rebuild)."""
    try:
        cutoff = time.time() - TRIM_CACHE_MAX_AGE_DAYS * 24 * 60 * 60
        if not TrimmedFontsFolderPath.exists():
            return
        for entry in TrimmedFontsFolderPath.iterdir():
            try:
                if entry.is_file():
                    if entry.stat().st_mtime < cutoff:
                        entry.unlink(missing_ok=True)
                elif entry.is_dir():
                    if entry.stat().st_mtime < cutoff:
                        for file_path in entry.iterdir():
                            file_path.unlink(missing_ok=True)
                        entry.rmdir()
            except Exception:
                continue
    except Exception:
        pass
