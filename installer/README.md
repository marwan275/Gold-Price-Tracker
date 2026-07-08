# GoldTracker Windows Installer

This folder contains the Inno Setup script for building a normal Windows installer for 24K Gold Tracker.

## Requirements

- Build the PyInstaller folder app first so `dist/GoldTracker/GoldTracker.exe` exists.
- Install Inno Setup 6 from https://jrsoftware.org/isinfo.php.
- Keep `assets/gold_tracker.ico` available because the installer and app executable use it as the icon.

## Build The App Folder

From the repository root, build the PyInstaller app folder:

```powershell
pyinstaller GoldTracker.spec
```

Confirm this file exists before compiling the installer:

```text
dist\GoldTracker\GoldTracker.exe
```

## Build The Installer

Open `GoldTracker.iss` in Inno Setup and click **Compile**.

Or, if `iscc.exe` is on PATH, run from the repository root:

```powershell
iscc installer\GoldTracker.iss
```

The installer output will be created as:

```text
dist\GoldTrackerSetup.exe
```

## Notes

- The installer installs the folder-style PyInstaller build, not a single-file executable.
- The installer app name is `GoldTracker`, while the user-facing window title is `24K Gold Tracker`.
- Rebuild the PyInstaller folder before compiling the installer whenever Python code, assets, or dependencies change.
