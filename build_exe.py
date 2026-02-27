"""
Build script for Blu Optical Simulation standalone executable.

Usage:
    python build_exe.py [--clean] [--zip]

Options:
    --clean     Remove previous build/dist directories before building
    --zip       Zip the output folder after a successful build

Requires:
    pip install pyinstaller
"""

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SPEC = ROOT / "BluOpticalSim.spec"
DIST_DIR = ROOT / "dist" / "BluOpticalSim"
BUILD_DIR = ROOT / "build"


def clean():
    for d in (BUILD_DIR, ROOT / "dist"):
        if d.exists():
            print(f"Removing {d} ...")
            shutil.rmtree(d)


def build():
    print("=" * 60)
    print("Building BluOpticalSim executable with PyInstaller ...")
    print("=" * 60)

    # Check pyinstaller is available
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("\nERROR: PyInstaller is not installed.")
        print("Run:  pip install pyinstaller")
        sys.exit(1)

    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm"],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        print("\nBuild FAILED.")
        sys.exit(result.returncode)

    print("\nBuild succeeded.")
    print(f"Output: {DIST_DIR}")


def make_zip():
    zip_path = ROOT / "dist" / "BluOpticalSim-windows.zip"
    print(f"\nCreating {zip_path.name} ...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file in DIST_DIR.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(DIST_DIR.parent))
    size_mb = zip_path.stat().st_size / 1_048_576
    print(f"Created {zip_path}  ({size_mb:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Build BluOpticalSim executable")
    parser.add_argument("--clean", action="store_true", help="Remove previous build artifacts first")
    parser.add_argument("--zip", action="store_true", help="Zip the dist folder after building")
    args = parser.parse_args()

    if args.clean:
        clean()

    build()

    if args.zip:
        make_zip()

    print("\nDone! Distribute the contents of:")
    print(f"  {DIST_DIR}")
    print("\nUsers just need to extract the folder and run BluOpticalSim.exe")


if __name__ == "__main__":
    main()
