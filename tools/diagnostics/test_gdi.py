import ctypes
gdi32 = ctypes.windll.gdi32
try:
    print(gdi32.GetEnhMetaFileHeader)
except Exception as e:
    print("Error:", e)
