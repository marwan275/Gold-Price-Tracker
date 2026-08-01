#!/usr/bin/env python3
"""
Unified build script for 24K-GoldTracker.
Reads version from pyproject.toml and builds both PyInstaller and Inno Setup installers.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import tomllib


def build():
    """Build the application and installer."""
    project_root = Path(__file__).parent

    # Clean up old builds
    print("Cleaning up old builds...")
    for directory in ["build", "dist"]:
        dir_path = project_root / directory
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"   ✓ Removed {directory}/")
    print()

    # Read version from pyproject.toml
    pyproject_path = project_root / "pyproject.toml"
    version = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))["project"][
        "version"
    ]
    print(f"Building 24K-GoldTracker v{version}\n")

    # Step 1: Generate ISS from template
    print("Generating installer config from template...")
    iss_template_path = project_root / "installer" / "24K-GoldTracker.iss.template"
    iss_content = iss_template_path.read_text(encoding="utf-8")
    iss_content = iss_content.replace("{VERSION}", version)

    iss_path = project_root / "installer" / "24K-GoldTracker.iss"
    iss_path.write_text(iss_content, encoding="utf-8")
    print(f"   ✓ Generated {iss_path.name}\n")

    # Step 2: Build with PyInstaller
    print("Building executable with PyInstaller...")
    result = subprocess.run(
        ["pyinstaller", "24K-GoldTracker.spec"],
        cwd=project_root,
        check=False,
    )
    if result.returncode != 0:
        print("\n   ✗ PyInstaller failed")
        return False
    print("   ✓ PyInstaller build complete\n")

    # Step 3: Compile installer with Inno Setup
    print("Compiling installer with Inno Setup...")
    iscc_path = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    result = subprocess.run(
        [iscc_path, str(iss_path)],
        cwd=project_root,
        check=False,
    )
    if result.returncode != 0:
        print("\n   ✗ Inno Setup failed")
        return False
    print("   ✓ Inno Setup compilation complete\n")

    # Summary
    print("=" * 50)
    print("Build successful!")
    print("=" * 50)
    print("\nOutputs:")
    exe_path = (
        project_root / f"dist/24K-GoldTracker-{version}/24K-GoldTracker-{version}.exe"
    )
    installer_path = project_root / f"dist/24K-GoldTrackerSetup-{version}.exe"

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"Executable: {exe_path}")
        print(f"     Size: {size_mb:.1f} MB")

    if installer_path.exists():
        size_mb = installer_path.stat().st_size / (1024 * 1024)
        print(f"Installer: {installer_path}")
        print(f"     Size: {size_mb:.1f} MB")

    return True


if __name__ == "__main__":
    success = build()
    sys.exit(0 if success else 1)
