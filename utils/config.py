import json
import os

from utils.path_helper import get_base_dir
CONFIG_FILE = os.path.join(get_base_dir(), "config.json")

DEFAULT_HOTKEYS = {
    "clipboard": "ctrl+shift+v",
    "screenshot": "win+shift+s",
    "smart_screenshot": "ctrl+shift+s",
    "notebook": "ctrl+shift+n",
    "toggle_ball": "ctrl+shift+b",
    "record": "ctrl+shift+r",
    "search": "ctrl+shift+f",
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
    "enable_search_ball": True,
    "enable_recent_ball": True,
    "clipboard_tracking_enabled": True,
    "clipboard_max_items": 20,
    "clipboard_max_images": 20,
    "record_text": True,
    "record_image": True,
    "hide_ball_when_screenshot": True,
    "video_save_path": "",
    "video_save_format": "mp4",
    "picture_save_path": "",
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
            hotkeys = config.get("hotkeys", {})
            for k, v in DEFAULT_HOTKEYS.items():
                if k not in hotkeys:
                    hotkeys[k] = v

            options = config.get("options", {})
            for k, v in DEFAULT_OPTIONS.items():
                if k not in options:
                    options[k] = v
            
            config["hotkeys"] = hotkeys
            config["options"] = options
            return config
    except Exception as e:
        print(f"Failed to load config: {e}")
        return {"hotkeys": DEFAULT_HOTKEYS, "options": DEFAULT_OPTIONS}

def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Failed to save config: {e}")
        return False

def load_hotkeys():
    return load_config().get("hotkeys", DEFAULT_HOTKEYS)

def load_options():
    return load_config().get("options", DEFAULT_OPTIONS)

def save_hotkeys(hotkeys_dict):
    config = load_config()
    config["hotkeys"] = hotkeys_dict
    save_config(config)

def save_option(option_name, value):
    config = load_config()
    options = config.get("options", DEFAULT_OPTIONS)
    options[option_name] = value
    config["options"] = options
    save_config(config)

