import os
import win32com.client

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
    except Exception:
        pass
        
    # Sort by modification time descending
    lnk_files.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in lnk_files]

def resolve_lnk_target(lnk_path):
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(lnk_path)
        target = shortcut.Targetpath
        return target
    except Exception:
        return None

def is_directory_target(target_path):
    return os.path.isdir(target_path)
