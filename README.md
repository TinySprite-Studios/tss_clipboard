# TSS Clipboard

Simple Windows clipboard saver app with Fallout-style terminal UI.

## Features
- Manual launch opens window immediately
- Global hotkey: `Alt + C` to show/hide
- Save up to 100 entries
- Left click entry to copy to Windows clipboard
- Right click entry to edit or delete
- Preview-only list (shows the start of each entry)
- Draggable custom-styled window
- In-app `SET` button with `Run on startup` checkbox
- Persistent storage in `clipboard_entries.json`

## Install
1. Download `TSS_Clippy.exe`.
2. Put it in any folder (for example `C:\Program Files\TSS Clipboard` or your Desktop).
3. Double-click the EXE to launch.
4. Open `SETTINGS (cog wheel)` and tick `Run on startup` if wanted, then click `SAVE`.

## Notes
- No Python install is needed.
- Startup launch runs hidden by design; use `Alt + C` to show/hide.
- If already running, launching again shows a message and keeps one instance only.

## Build EXE (optional)
```powershell
pip install pyinstaller
pyinstaller --clean --noconsole --onefile --name "TSS-Clipboard" --icon "assets\images\clipboard_logo.ico" --add-data "assets\images\clipboard_logo.png;assets\images" app.py
```
The executable will be under `dist\TSS_Clippy.exe`.

