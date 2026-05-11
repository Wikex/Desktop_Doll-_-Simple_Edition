import ctypes
from ctypes import wintypes
import win32clipboard

user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
user32.GetClipboardData.restype = wintypes.HANDLE
user32.GetClipboardData.argtypes = [wintypes.UINT]

CF_ENHMETAFILE = 14

win32clipboard.OpenClipboard()
hemf = user32.GetClipboardData(CF_ENHMETAFILE)
print("HEMF:", hemf)

if hemf:
    class ENHMETAHEADER(ctypes.Structure):
        _fields_ = [("iType", wintypes.DWORD), ("nSize", wintypes.DWORD),
                    ("rclBounds", wintypes.RECT), ("rclFrame", wintypes.RECT)]
    header = ENHMETAHEADER()
    gdi32.GetEnhMetaFileHeaderW(hemf, ctypes.sizeof(header), ctypes.byref(header))
    print("rclBounds:", header.rclBounds.left, header.rclBounds.top, header.rclBounds.right, header.rclBounds.bottom)
    print("rclFrame:", header.rclFrame.left, header.rclFrame.top, header.rclFrame.right, header.rclFrame.bottom)

win32clipboard.CloseClipboard()
