# Diagnostics Scripts

This folder keeps ad-hoc clipboard, hotkey, GDI, and Windows API diagnostics out of the application root.

These scripts are not part of the normal app startup path.

## Categories

- `dump_*`: inspect clipboard, UI, or rendering state.
- `wait_*`: helper scripts for manual reproduction with external apps.
- `test_*`: lightweight manual diagnostics for OCR, hotkeys, clipboard, GDI, and Qt behavior.

Run these scripts only when debugging a specific issue. They are not required for packaging or normal use.
