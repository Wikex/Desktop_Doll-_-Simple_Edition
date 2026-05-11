def parse_hotkey(key_str):
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_WIN = 0x0008
    mods = 0
    vk = 0
    parts = key_str.lower().split('+')
    for p in parts:
        p = p.strip()
        if p in ('ctrl', 'control'): mods |= MOD_CONTROL
        elif p == 'shift': mods |= MOD_SHIFT
        elif p == 'alt': mods |= MOD_ALT
        elif p in ('win', 'windows'): mods |= MOD_WIN
        else:
            if len(p) == 1 and 'a' <= p <= 'z':
                vk = ord(p.upper())
            elif len(p) == 1 and '0' <= p <= '9':
                vk = ord(p)
            elif p.startswith('f') and p[1:].isdigit():
                vk = 0x6F + int(p[1:])
            elif p == 'space': vk = 0x20
            elif p in ('esc', 'escape'): vk = 0x1B
            elif p in ('enter', 'return'): vk = 0x0D
            elif p == 'tab': vk = 0x09
            elif p == 'up': vk = 0x26
            elif p == 'down': vk = 0x28
            elif p == 'left': vk = 0x25
            elif p == 'right': vk = 0x27
    return mods, vk

print(parse_hotkey("ctrl+shift+a"))
print(parse_hotkey("win+shift+s"))
print(parse_hotkey("alt+f4"))
