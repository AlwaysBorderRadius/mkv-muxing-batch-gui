import json
from pathlib import Path

from PySide6.QtWidgets import QWidget

from packages.Startup.GlobalFiles import SettingJsonInfoFilePath
from packages.Widgets.SingleDefaultPresetsData import SingleDefaultPresetsData


def get_data_from_json(json_data, attribute, default_value):
    try:
        return json_data[attribute]
    except Exception:
        return default_value


def get_names_list_of_presets():
    names_list = []
    for preset in Options.DefaultPresets:
        names_list.append(preset.Preset_Name)
    return names_list


DEFAULT_SUBTITLE_KARAOKE_STYLE_KEYWORDS = [
    "kara",
    "karaoke",
    "romaji",
    "op",
    "ed",
    "song",
    "opening",
    "ending",
    "note",
    "sign",
    "signs",
]
DEFAULT_SUBTITLE_KARAOKE_EFFECT_KEYWORDS = ["karaoke", "fx"]


def normalize_keywords_list(keywords) -> list[str]:
    if not isinstance(keywords, list):
        return []
    normalized_keywords = []
    for keyword in keywords:
        keyword_text = str(keyword).strip().lower()
        if keyword_text:
            normalized_keywords.append(keyword_text)
    return normalized_keywords


def parse_keywords_text(text: str) -> list[str]:
    parsed_keywords = []
    for keyword in text.split(","):
        keyword_text = keyword.strip().lower()
        if keyword_text:
            parsed_keywords.append(keyword_text)
    return parsed_keywords


def normalize_track_names_list(names) -> list[str]:
    if not isinstance(names, list):
        return []
    normalized_names = []
    for name in names:
        name_text = str(name).strip()
        if name_text and name_text not in normalized_names:
            normalized_names.append(name_text)
    return normalized_names


class Options(QWidget):
    DefaultPresets = [SingleDefaultPresetsData()]
    CurrentPreset = SingleDefaultPresetsData()
    FavoritePresetId = 0
    Dark_Mode = False
    Attachment_Expert_Mode_Info_Message_Show = True
    Attachment_Filter_Unused_Fonts = False
    Attachment_Trim_Unused_Glyphs = False
    Choose_Preset_On_Startup = False
    Subtitle_Karaoke_Tag_Filter = True
    Subtitle_Karaoke_Style_Keywords = DEFAULT_SUBTITLE_KARAOKE_STYLE_KEYWORDS.copy()
    Subtitle_Karaoke_Effect_Keywords = DEFAULT_SUBTITLE_KARAOKE_EFFECT_KEYWORDS.copy()
    Subtitle_Favorite_Track_Names = []


def save_options():
    default_presets_data = []
    for preset_id in range(len(Options.DefaultPresets)):
        temp_default_preset = {
            "Preset_Name": Options.DefaultPresets[preset_id].Preset_Name,
            "Default_Video_Directory": Options.DefaultPresets[
                preset_id
            ].Default_Video_Directory,
            "Default_Video_Extensions": Options.DefaultPresets[
                preset_id
            ].Default_Video_Extensions,
            "Default_Subtitle_Directory": Options.DefaultPresets[
                preset_id
            ].Default_Subtitle_Directory,
            "Default_Subtitle_Extensions": Options.DefaultPresets[
                preset_id
            ].Default_Subtitle_Extensions,
            "Default_Subtitle_Language": Options.DefaultPresets[
                preset_id
            ].Default_Subtitle_Language,
            "Default_Audio_Directory": Options.DefaultPresets[
                preset_id
            ].Default_Audio_Directory,
            "Default_Audio_Extensions": Options.DefaultPresets[
                preset_id
            ].Default_Audio_Extensions,
            "Default_Audio_Language": Options.DefaultPresets[
                preset_id
            ].Default_Audio_Language,
            "Default_Chapter_Directory": Options.DefaultPresets[
                preset_id
            ].Default_Chapter_Directory,
            "Default_Chapter_Extensions": Options.DefaultPresets[
                preset_id
            ].Default_Chapter_Extensions,
            "Default_Attachment_Directory": Options.DefaultPresets[
                preset_id
            ].Default_Attachment_Directory,
            "Default_Destination_Directory": Options.DefaultPresets[
                preset_id
            ].Default_Destination_Directory,
            "Default_Favorite_Subtitle_Languages": Options.DefaultPresets[
                preset_id
            ].Default_Favorite_Subtitle_Languages,
            "Default_Favorite_Audio_Languages": Options.DefaultPresets[
                preset_id
            ].Default_Favorite_Audio_Languages,
        }
        default_presets_data.append(temp_default_preset)
    options_data = {
        "Presets": default_presets_data,
        "FavoritePresetId": Options.FavoritePresetId,
        "Dark_Mode": Options.Dark_Mode,
        "Attachment_Expert_Mode_Info_Message_Show": Options.Attachment_Expert_Mode_Info_Message_Show,
        "Attachment_Filter_Unused_Fonts": Options.Attachment_Filter_Unused_Fonts,
        "Attachment_Trim_Unused_Glyphs": Options.Attachment_Trim_Unused_Glyphs,
        "Choose_Preset_On_Startup": Options.Choose_Preset_On_Startup,
        "Subtitle_Karaoke_Tag_Filter": Options.Subtitle_Karaoke_Tag_Filter,
        "Subtitle_Karaoke_Style_Keywords": Options.Subtitle_Karaoke_Style_Keywords,
        "Subtitle_Karaoke_Effect_Keywords": Options.Subtitle_Karaoke_Effect_Keywords,
        "Subtitle_Favorite_Track_Names": Options.Subtitle_Favorite_Track_Names,
    }
    options_file_path = Path(SettingJsonInfoFilePath)
    with open(options_file_path, "w+", encoding="UTF-8") as option_file:
        json.dump(options_data, option_file, indent=4)


def read_option_file(option_file):
    option_file_path = Path(option_file)
    if option_file_path.is_file():
        with open(option_file_path, "r+", encoding="UTF-8") as option_file:
            data = json.load(option_file)
            presets = get_data_from_json(
                json_data=data, attribute="Presets", default_value="Old"
            )
            if presets == "Old":
                preset_number = 1
            else:
                preset_number = len(presets)
            Options.DefaultPresets.clear()
            for preset_id in range(preset_number):
                temp_default_preset = SingleDefaultPresetsData()
                temp_default_preset.Preset_Name = get_data_from_json(
                    json_data=presets[preset_id],
                    attribute="Preset_Name",
                    default_value=f"Preset #{preset_id + 1}",
                )
                temp_default_preset.Default_Video_Directory = get_data_from_json(
                    json_data=presets[preset_id],
                    attribute="Default_Video_Directory",
                    default_value="",
                )
                temp_default_preset.Default_Video_Extensions = get_data_from_json(
                    json_data=presets[preset_id],
                    attribute="Default_Video_Extensions",
                    default_value=["MKV"],
                )
                temp_default_preset.Default_Subtitle_Directory = get_data_from_json(
                    json_data=presets[preset_id],
                    attribute="Default_Subtitle_Directory",
                    default_value="",
                )
                temp_default_preset.Default_Subtitle_Extensions = get_data_from_json(
                    json_data=presets[preset_id],
                    attribute="Default_Subtitle_Extensions",
                    default_value=["ASS"],
                )
                temp_default_preset.Default_Subtitle_Language = get_data_from_json(
                    json_data=presets[preset_id],
                    attribute="Default_Subtitle_Language",
                    default_value="English",
                )
                temp_default_preset.Default_Audio_Directory = get_data_from_json(
                    json_data=presets[preset_id],
                    attribute="Default_Audio_Directory",
                    default_value="",
                )
                temp_default_preset.Default_Audio_Extensions = get_data_from_json(
                    json_data=presets[preset_id],
                    attribute="Default_Audio_Extensions",
                    default_value=["AAC"],
                )
                temp_default_preset.Default_Audio_Language = get_data_from_json(
                    json_data=presets[preset_id],
                    attribute="Default_Audio_Language",
                    default_value="English",
                )
                temp_default_preset.Default_Chapter_Directory = get_data_from_json(
                    json_data=presets[preset_id],
                    attribute="Default_Chapter_Directory",
                    default_value="",
                )
                temp_default_preset.Default_Chapter_Extensions = get_data_from_json(
                    json_data=presets[preset_id],
                    attribute="Default_Chapter_Extensions",
                    default_value=["XML"],
                )
                temp_default_preset.Default_Attachment_Directory = get_data_from_json(
                    json_data=presets[preset_id],
                    attribute="Default_Attachment_Directory",
                    default_value="",
                )
                temp_default_preset.Default_Destination_Directory = get_data_from_json(
                    json_data=presets[preset_id],
                    attribute="Default_Destination_Directory",
                    default_value="",
                )
                temp_default_preset.Default_Favorite_Subtitle_Languages = (
                    get_data_from_json(
                        json_data=presets[preset_id],
                        attribute="Default_Favorite_Subtitle_Languages",
                        default_value=["English", "Arabic"],
                    )
                )
                temp_default_preset.Default_Favorite_Audio_Languages = get_data_from_json(
                    json_data=presets[preset_id],
                    attribute="Default_Favorite_Audio_Languages",
                    default_value=["English", "Arabic"],
                )
                Options.DefaultPresets.append(temp_default_preset)
            Options.FavoritePresetId = get_data_from_json(
                json_data=data, attribute="FavoritePresetId", default_value=0
            )
            Options.Dark_Mode = get_data_from_json(
                json_data=data, attribute="Dark_Mode", default_value=False
            )
            Options.Attachment_Expert_Mode_Info_Message_Show = get_data_from_json(
                json_data=data,
                attribute="Attachment_Expert_Mode_Info_Message_Show",
                default_value=True,
            )
            Options.Attachment_Filter_Unused_Fonts = get_data_from_json(
                json_data=data,
                attribute="Attachment_Filter_Unused_Fonts",
                default_value=False,
            )
            Options.Attachment_Trim_Unused_Glyphs = get_data_from_json(
                json_data=data,
                attribute="Attachment_Trim_Unused_Glyphs",
                default_value=False,
            )
            Options.Choose_Preset_On_Startup = get_data_from_json(
                json_data=data, attribute="Choose_Preset_On_Startup", default_value=False
            )
            Options.Subtitle_Karaoke_Tag_Filter = get_data_from_json(
                json_data=data,
                attribute="Subtitle_Karaoke_Tag_Filter",
                default_value=True,
            )
            Options.Subtitle_Karaoke_Style_Keywords = normalize_keywords_list(
                get_data_from_json(
                    json_data=data,
                    attribute="Subtitle_Karaoke_Style_Keywords",
                    default_value=DEFAULT_SUBTITLE_KARAOKE_STYLE_KEYWORDS,
                )
            )
            Options.Subtitle_Karaoke_Effect_Keywords = normalize_keywords_list(
                get_data_from_json(
                    json_data=data,
                    attribute="Subtitle_Karaoke_Effect_Keywords",
                    default_value=DEFAULT_SUBTITLE_KARAOKE_EFFECT_KEYWORDS,
                )
            )
            Options.Subtitle_Favorite_Track_Names = normalize_track_names_list(
                get_data_from_json(
                    json_data=data,
                    attribute="Subtitle_Favorite_Track_Names",
                    default_value=[],
                )
            )
    save_options()
