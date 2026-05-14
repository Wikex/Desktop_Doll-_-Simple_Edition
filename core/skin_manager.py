import os
import json
import copy
from PySide6.QtCore import QObject, Signal
from utils.path_helper import get_base_dir
from utils.logger import log_exception

DEFAULT_SKIN_CONFIG = {
    "name": "简洁性能样式",
    "type": "code",
    "performance": {
        "animations": False,
        "use_gradients": False,
        "screenshot_debug_overlay": False
    },
    "main_ball": {
        "size": [56, 56],
        "color": [37, 99, 235, 230],
        "border_color": [255, 255, 255, 90],
        "edge_hide": {
            "enabled": True,
            "trigger_margin": 16,
            "visible_width": 10,
            "restore_margin": 8
        },
        "locator": {
            "renderer": "qt_ripple",
            "size": 180,
            "duration_ms": 1600,
            "interval_ms": 33,
            "live2d_asset": ""
        }
    },
    "sub_ball": {
        "size": [34, 34],
        "font_size": 10,
        "icon_size": 20,
        "border_color": [255, 255, 255, 80],
        "colors": {
            "clipboard": [245, 158, 11, 230],
            "screenshot": [34, 197, 94, 230],
            "notebook": [59, 130, 246, 230],
            "smart_screenshot": [239, 68, 68, 230],
            "record": [220, 38, 38, 230],
            "record_active": [34, 197, 94, 230],
            "recent": [20, 184, 166, 230],
            "custom": [100, 116, 139, 230]
        }
    },
    "layout": {
        "first_ring_radius": 54,
        "ring_spacing": 42,
        "ball_gap": 42,
        "max_drag_radius": 145
    },
    "panel": {
        "size": [300, 390],
        "radius": 6,
        "margin": 8,
        "item_radius": 4,
        "item_height": 58
    },
    "settings": {
        "size": [560, 440],
        "radius": 6,
        "compact": True
    }
}


def _deep_merge(defaults, override):
    merged = copy.deepcopy(defaults)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class SkinManager(QObject):
    skin_changed = Signal(dict)

    def __init__(self, current_skin="default", parent=None):
        super().__init__(parent)
        self.skins_dir = os.path.join(get_base_dir(), "skins")
        self._ensure_default_skin()
        self.current_skin_name = current_skin
        self.current_skin_config = self._load_skin(self.current_skin_name)

    def _ensure_default_skin(self):
        if not os.path.exists(self.skins_dir):
            os.makedirs(self.skins_dir, exist_ok=True)
            
        default_dir = os.path.join(self.skins_dir, "default")
        os.makedirs(default_dir, exist_ok=True)
        default_skin_path = os.path.join(default_dir, "skin.json")
        if not os.path.exists(default_skin_path):
            with open(default_skin_path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_SKIN_CONFIG, f, indent=4, ensure_ascii=False)

    def _load_skin(self, name):
        skin_path = os.path.join(self.skins_dir, name, "skin.json")
        if os.path.exists(skin_path):
            try:
                with open(skin_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    config["_path"] = os.path.join(self.skins_dir, name)
                    return _deep_merge(DEFAULT_SKIN_CONFIG, config)
            except Exception as e:
                log_exception(f"Failed to load skin {name}: {e}")
                
        fallback = copy.deepcopy(DEFAULT_SKIN_CONFIG)
        fallback["_path"] = ""
        return fallback

    def get_available_skins(self):
        if not os.path.exists(self.skins_dir):
            return ["default"]
        skins = []
        for d in os.listdir(self.skins_dir):
            if os.path.isdir(os.path.join(self.skins_dir, d)):
                if os.path.exists(os.path.join(self.skins_dir, d, "skin.json")):
                    skins.append(d)
        if "default" not in skins:
            skins.insert(0, "default")
        return skins

    def set_skin(self, name):
        if name != self.current_skin_name:
            self.current_skin_name = name
            self.current_skin_config = self._load_skin(name)
            self.skin_changed.emit(self.current_skin_config)

    def get_skin_config(self):
        return self.current_skin_config
