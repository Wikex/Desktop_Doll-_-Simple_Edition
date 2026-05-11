import win32clipboard
import win32gui
import win32process
import psutil

try:
    win32clipboard.OpenClipboard()
    owner_hwnd = win32clipboard.GetClipboardOwner()
    win32clipboard.CloseClipboard()
    
    if owner_hwnd:
        _, pid = win32process.GetWindowThreadProcessId(owner_hwnd)
        process = psutil.Process(pid)
        print("Clipboard Owner:", process.name())
    else:
        print("No clipboard owner.")
except Exception as e:
    print("Error:", e)
