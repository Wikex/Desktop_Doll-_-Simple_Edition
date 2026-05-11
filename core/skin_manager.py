import os
import json
from PySide6.QtCore import QObject, Signal
from utils.path_helper import get_base_dir
from utils.logger import log_exception

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
        if not os.path.exists(default_dir):
            os.makedirs(default_dir, exist_ok=True)
            default_config = {
                "name": "默认样式",
                "type": "code",
                "main_ball": {
                    "size": [60, 60]
                },
                "sub_ball": {
                    "size": [36, 36]
                }
            }
            with open(os.path.join(default_dir, "skin.json"), "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)

    def _load_skin(self, name):
        skin_path = os.path.join(self.skins_dir, name, "skin.json")
        if os.path.exists(skin_path):
            try:
                with open(skin_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    config["_path"] = os.path.join(self.skins_dir, name)
                    return config
            except Exception as e:
                log_exception(f"Failed to load skin {name}: {e}")
                
        # Fallback to default
        return {"type": "code", "_path": "", "main_ball": {"size": [60, 60]}, "sub_ball": {"size": [36, 36]}}

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
