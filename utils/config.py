import json
import os
from typing import Any, Literal, TypedDict

from utils.path_helper import get_base_dir
from utils.logger import log_exception
CONFIG_FILE = os.path.join(get_base_dir(), "config.json")

HotkeyKey = Literal[
    "clipboard",
    "screenshot",
    "smart_screenshot",
    "notebook",
    "toggle_ball",
    "locate_ball",
    "toggle_panels",
    "record",
    "recent",
]

OptionKey = Literal[
    "hide_ball_when_screenshot",
    "clipboard_max_items",
    "clipboard_tracking_enabled",
    "video_save_path",
    "picture_save_path",
    "clipboard_max_images",
    "clipboard_content_type",
    "browser_path",
    "enable_clipboard_ball",
    "enable_screenshot_ball",
    "enable_notebook_ball",
    "enable_smart_screenshot_ball",
    "enable_record_ball",
    "enable_recent_ball",
    "record_text",
    "record_image",
    "video_save_format",
    "custom_apps",
    "recent_tracking_enabled",
    "recent_max_items",
    "recent_excluded_extensions",
    "recent_extension_visibility",
]


class AppConfig(TypedDict):
    hotkeys: dict[HotkeyKey, str]
    options: dict[OptionKey, Any]

DEFAULT_HOTKEYS = {
    "clipboard": "ctrl+shift+v",
    "screenshot": "win+shift+s",
    "smart_screenshot": "ctrl+shift+s",
    "notebook": "ctrl+shift+n",
    "toggle_ball": "ctrl+shift+b",
    "locate_ball": "ctrl+shift+l",
    "toggle_panels": "",
    "record": "ctrl+shift+r",
    "recent": ""
}

DEFAULT_OPTIONS = {
    "hide_ball_when_screenshot": True,
    "clipboard_max_items": 20,
    "clipboard_tracking_enabled": True,
    "video_save_path": "",
    "picture_save_path": "",
    "clipboard_max_images": 20,
    "clipboard_content_type": "both",
    "browser_path": "msedge",
    "enable_clipboard_ball": True,
    "enable_screenshot_ball": True,
    "enable_notebook_ball": True,
    "enable_smart_screenshot_ball": True,
    "enable_record_ball": True,
    "enable_recent_ball": True,
    "record_text": True,
    "record_image": True,
    "video_save_format": "mp4",
    "custom_apps": [],
    "recent_tracking_enabled": True,
    "recent_max_items": 30,
    "recent_excluded_extensions": {},
    "recent_extension_visibility": {}
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"hotkeys": DEFAULT_HOTKEYS, "options": DEFAULT_OPTIONS}
        
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            
            # Merge with defaults in case new keys were added in later versions
            loaded_hotkeys = config.get("hotkeys", {})
            hotkeys = {
                k: loaded_hotkeys.get(k, v)
                for k, v in DEFAULT_HOTKEYS.items()
            }

            loaded_options = config.get("options", {})
            options = {
                k: loaded_options.get(k, v)
                for k, v in DEFAULT_OPTIONS.items()
            }
            
            config["hotkeys"] = hotkeys
            config["options"] = options
            return config
    except Exception as e:
        log_exception(f"Failed to load config: {e}")
        return {"hotkeys": DEFAULT_HOTKEYS, "options": DEFAULT_OPTIONS}

def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        log_exception(f"Failed to save config: {e}")
        return False

def load_hotkeys():
    return load_config().get("hotkeys", DEFAULT_HOTKEYS)

def load_options():
    return load_config().get("options", DEFAULT_OPTIONS)

def save_hotkeys(hotkeys_dict):
    config = load_config()
    config["hotkeys"] = hotkeys_dict
    save_config(config)

def save_option(option_name: OptionKey, value: Any):
    config = load_config()
    options = config.get("options", DEFAULT_OPTIONS)
    options[option_name] = value
    config["options"] = options
    save_config(config)

