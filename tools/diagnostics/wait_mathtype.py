import time
import win32clipboard

print("\n" + "="*50)
print("PLEASE COPY A MATHTYPE EQUATION NOW!")
print("等待中... 请在 MathType 中选中一个公式并按下 Ctrl+C")
print("="*50 + "\n")

def get_formats():
    win32clipboard.OpenClipboard()
    formats = []
    f = win32clipboard.EnumClipboardFormats(0)
    while f:
        try:
            name = win32clipboard.GetClipboardFormatName(f)
            formats.append(f"{name} ({f})")
        except:
            if f == 1: formats.append("CF_TEXT (1)")
            elif f == 2: formats.append("CF_BITMAP (2)")
            elif f == 3: formats.append("CF_METAFILEPICT (3)")
            elif f == 8: formats.append("CF_DIB (8)")
            elif f == 13: formats.append("CF_UNICODETEXT (13)")
            elif f == 14: formats.append("CF_ENHMETAFILE (14)")
            else: formats.append(str(f))
        f = win32clipboard.EnumClipboardFormats(f)
    win32clipboard.CloseClipboard()
    return formats

try:
    initial = get_formats()
except:
    initial = []

while True:
    try:
        current = get_formats()
        if current != initial:
            print("\nClipboard changed! Captured MathType formats:")
            for f in current:
                print(" -", f)
            break
    except:
        pass
    time.sleep(0.5)
