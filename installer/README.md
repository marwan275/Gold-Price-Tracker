# 24K-GoldTracker Windows Installer

This folder contains the Inno Setup script for building a normal Windows installer for 24K-GoldTracker.

## Requirements

- Build the PyInstaller folder app first so `dist/24K-GoldTracker/24K-GoldTracker.exe` exists.
- Install Inno Setup 6 from https://jrsoftware.org/isinfo.php.
- Keep `assets/gold_tracker.png` available because the running app window loads that file as its icon.

## Build The App Folder

From the repository root, build the PyInstaller app folder:

```powershell
pyinstaller 24K-GoldTracker.spec
```

Confirm this file exists before compiling the installer:

```text
dist\24K-GoldTracker-1.1.0\24K-GoldTracker-1.1.0.exe
```

## Build The Installer

Open `24K-GoldTracker.iss` in Inno Setup and click **Compile**.

Or, if `iscc.exe` is on PATH, run from the repository root:

```powershell
iscc installer\24K-GoldTracker.iss
```

The installer output will be created as:

```text
dist\24K-GoldTrackerSetup-1.1.0.exe
```

## Notes

- The installer installs the folder-style PyInstaller build, not a single-file executable.
- The installer app name and the user-facing window title are both `24K-GoldTracker`.
- Rebuild the PyInstaller folder before compiling the installer whenever Python code, assets, or dependencies change.
