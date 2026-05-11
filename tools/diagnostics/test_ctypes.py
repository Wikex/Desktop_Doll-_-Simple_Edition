import ctypes
from ctypes import wintypes
user32 = ctypes.windll.user32
print(user32.GetClipboardData.restype)
