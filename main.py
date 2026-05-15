import sys
import os
import time

from app_controller import FloatingAssistant


SINGLE_INSTANCE_MUTEX = None
RESTART_WAIT_ENV = "DESKTOP_DOLL_RESTART_WAIT_PID"


def wait_for_restart_parent():
    parent_pid = os.environ.pop(RESTART_WAIT_ENV, "")
    if not parent_pid:
        return
    try:
        pid = int(parent_pid)
    except ValueError:
        return
    if pid <= 0 or pid == os.getpid():
        return

    try:
        import ctypes

        synchronize = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)
        if handle:
            try:
                ctypes.windll.kernel32.WaitForSingleObject(handle, 15000)
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
            return
    except Exception:
        pass

    time.sleep(1.5)


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
    wait_for_restart_parent()
    SINGLE_INSTANCE_MUTEX = ensure_single_instance()
    assistant = FloatingAssistant()
    sys.exit(assistant.run())
