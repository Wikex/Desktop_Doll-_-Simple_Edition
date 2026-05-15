import os
import win32com.client
import winreg
from utils.logger import log_exception

def ensure_windows_recent_tracking_enabled():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
        try:
            value, _ = winreg.QueryValueEx(key, "Start_TrackDocs")
            if value == 0:
                winreg.SetValueEx(key, "Start_TrackDocs", 0, winreg.REG_DWORD, 1)
        except FileNotFoundError:
            winreg.SetValueEx(key, "Start_TrackDocs", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)
    except Exception as e:
        log_exception(f"Failed to enable Windows recent tracking: {e}")

def get_recent_dir():
    return os.path.join(os.environ.get('APPDATA', ''), r'Microsoft\Windows\Recent')

def list_recent_lnk_files():
    recent_dir = get_recent_dir()
    if not os.path.exists(recent_dir):
        return []
    
    lnk_files = []
    try:
        for entry in os.scandir(recent_dir):
            if entry.is_file() and entry.name.lower().endswith('.lnk'):
                lnk_files.append((entry.path, entry.stat().st_mtime))
    except Exception as e:
        log_exception(f"Failed to scan Windows Recent folder: {e}")
        
    # Sort by modification time descending
    lnk_files.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in lnk_files]

def resolve_lnk_target(lnk_path, shell=None):
    try:
        shell = shell or win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(lnk_path)
        target = shortcut.Targetpath
        return target
    except Exception as e:
        log_exception(f"Failed to resolve shortcut target: {e}")
        return None

def is_directory_target(target_path):
    return os.path.isdir(target_path)
