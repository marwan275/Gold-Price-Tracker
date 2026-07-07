# GoldTracker Windows Installer

This folder contains the Inno Setup script for building a normal Windows installer.

## Requirements

- Build the PyInstaller folder app first so `dist/GoldTracker/GoldTracker.exe` exists.
- Install Inno Setup 6 from https://jrsoftware.org/isinfo.php.

## Build

Open `GoldTracker.iss` in Inno Setup and click **Compile**.

Or, if `iscc.exe` is on PATH, run from the repository root:

```powershell
iscc installer\GoldTracker.iss
```

The installer output will be created as:

```text
dist\GoldTrackerSetup.exe
```
