import win32clipboard
import time

print("Waiting for clipboard change... Please copy a text box in PPT NOW.")

def get_formats():
    win32clipboard.OpenClipboard()
    formats = []
    f = win32clipboard.EnumClipboardFormats(0)
    while f:
        try:
            name = win32clipboard.GetClipboardFormatName(f)
            formats.append(f"{name} ({f})")
        except:
            formats.append(str(f))
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
            print("\nClipboard changed! Formats:")
            for f in current:
                print(" -", f)
            break
    except:
        pass
    time.sleep(0.5)
