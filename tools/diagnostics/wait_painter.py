import time
import win32clipboard

print("Waiting for clipboard change... Please click the Format Painter (格式刷) in WPS Office NOW.")

def get_formats():
    win32clipboard.OpenClipboard()
    formats = []
    f = win32clipboard.EnumClipboardFormats(0)
    while f:
        try:
            name = win32clipboard.GetClipboardFormatName(f)
            formats.append(name)
        except:
            formats.append(str(f))
        f = win32clipboard.EnumClipboardFormats(f)
    win32clipboard.CloseClipboard()
    return formats

# initial
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
