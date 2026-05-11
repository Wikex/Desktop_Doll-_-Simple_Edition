import sys

from app_controller import FloatingAssistant


def ensure_single_instance():
    import ctypes
    import win32api
    import win32event
    import winerror

    mutex_name = "DesktopAssistantUniqueMutex_1_0"
    mutex = win32event.CreateMutex(None, 1, mutex_name)
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        ctypes.windll.user32.MessageBoxW(0, "桌面人偶已经在运行中。", "提示", 0x30)
        sys.exit(0)
    return mutex


if __name__ == "__main__":
    ensure_single_instance()
    assistant = FloatingAssistant()
    sys.exit(assistant.run())
