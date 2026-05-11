MODIFIER_KEYS = ["ctrl", "shift", "alt", "windows", "left windows", "right windows"]


def release_modifier_keys(keyboard_module):
    for key in MODIFIER_KEYS:
        try:
            keyboard_module.release(key)
        except ValueError:
            pass
