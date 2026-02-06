#!/usr/bin/env python3
"""
Build MyNotes come eseguibile standalone portabile.

Uso:
    python build_portable.py

Requisiti:
    pip install pyinstaller pillow

Crea una cartella dist/MyNotes/ con l'eseguibile e tutto il necessario.
Copia quella cartella su una chiavetta USB e funziona ovunque.
"""

import subprocess
import sys
import os
import shutil
import platform

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(SCRIPT_DIR, "dist")
BUILD_DIR = os.path.join(SCRIPT_DIR, "build")


def check_pyinstaller():
    try:
        import PyInstaller
        return True
    except ImportError:
        print("PyInstaller non trovato. Installazione in corso...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        return True


def build():
    check_pyinstaller()

    is_windows = sys.platform == "win32"
    separator = ";" if is_windows else ":"

    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "MyNotes",
        "--onedir",
        "--windowed",           # no console window
        "--noconfirm",          # overwrite without asking
        "--clean",              # clean build cache
        # Add all Python source files
        "--add-data", f"database.py{separator}.",
        "--add-data", f"gui.py{separator}.",
        "--add-data", f"dialogs.py{separator}.",
        "--add-data", f"image_utils.py{separator}.",
        "--add-data", f"platform_utils.py{separator}.",
        "--add-data", f"annotator.py{separator}.",
        "--add-data", f"updater.py{separator}.",
        "--add-data", f"version.py{separator}.",
        "--add-data", f"crypto_utils.py{separator}.",
        "--add-data", f"backup_utils.py{separator}.",
        # Hidden imports
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.ImageDraw",
        "--hidden-import", "PIL.ImageFont",
        "--hidden-import", "PIL.ImageGrab",
        # Entry point
        "main.py",
    ]

    print(f"Building MyNotes per {platform.system()}...")
    print(f"Comando: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, cwd=SCRIPT_DIR)

    if result.returncode != 0:
        print("\nERRORE: Build fallita!")
        sys.exit(1)

    # Create data directory in dist
    dist_app = os.path.join(DIST_DIR, "MyNotes")
    data_dir = os.path.join(dist_app, "data")
    att_dir = os.path.join(data_dir, "attachments")
    os.makedirs(att_dir, exist_ok=True)

    # Copy launchers
    for f in ["run.sh", "run.bat"]:
        src = os.path.join(SCRIPT_DIR, f)
        if os.path.exists(src):
            shutil.copy2(src, dist_app)

    print()
    print("=" * 50)
    print("BUILD COMPLETATA!")
    print("=" * 50)
    print(f"Cartella: {dist_app}")
    print()
    print("Copia la cartella dist/MyNotes/ su una chiavetta USB.")
    print()
    if is_windows:
        print("Per avviare: doppio click su MyNotes.exe")
    else:
        print("Per avviare: ./MyNotes o doppio click su MyNotes")
    print()


if __name__ == "__main__":
    build()
