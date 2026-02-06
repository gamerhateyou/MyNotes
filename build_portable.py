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


def inject_oauth_credentials():
    """Inject OAuth credentials from env vars into backup_utils.py before build."""
    client_id = os.environ.get("MYNOTES_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("MYNOTES_OAUTH_CLIENT_SECRET", "")
    if not client_id:
        print("NOTA: MYNOTES_OAUTH_CLIENT_ID non impostato, Google Drive non funzionera'")
        return

    path = os.path.join(SCRIPT_DIR, "backup_utils.py")
    with open(path, "r") as f:
        content = f.read()

    content = content.replace(
        'os.environ.get("MYNOTES_OAUTH_CLIENT_ID", "")',
        f'os.environ.get("MYNOTES_OAUTH_CLIENT_ID", "{client_id}")',
    )
    content = content.replace(
        'os.environ.get("MYNOTES_OAUTH_CLIENT_SECRET", "")',
        f'os.environ.get("MYNOTES_OAUTH_CLIENT_SECRET", "{client_secret}")',
    )

    with open(path, "w") as f:
        f.write(content)
    print(f"OAuth credentials iniettati in backup_utils.py")


def build():
    check_pyinstaller()
    inject_oauth_credentials()

    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "MyNotes",
        "--onedir",
        "--windowed",           # no console window
        "--noconfirm",          # overwrite without asking
        "--clean",              # clean build cache
        # Tell PyInstaller where to find local modules
        "--paths", ".",
        # Local modules
        "--hidden-import", "database",
        "--hidden-import", "gui",
        "--hidden-import", "gui.constants",
        "--hidden-import", "gui.menu",
        "--hidden-import", "gui.layout",
        "--hidden-import", "gui.note_controller",
        "--hidden-import", "gui.export_controller",
        "--hidden-import", "gui.media_controller",
        "--hidden-import", "gui.backup_controller",
        "--hidden-import", "gui.update_controller",
        "--hidden-import", "dialogs",
        "--hidden-import", "image_utils",
        "--hidden-import", "platform_utils",
        "--hidden-import", "annotator",
        "--hidden-import", "updater",
        "--hidden-import", "version",
        "--hidden-import", "crypto_utils",
        "--hidden-import", "backup_utils",
        "--hidden-import", "audio_utils",
        "--hidden-import", "error_codes",
        # PIL
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.ImageDraw",
        "--hidden-import", "PIL.ImageFont",
        "--hidden-import", "PIL.ImageGrab",
        # Google Drive
        "--hidden-import", "google.oauth2.credentials",
        "--hidden-import", "google.auth.transport.requests",
        "--hidden-import", "google_auth_oauthlib.flow",
        "--hidden-import", "googleapiclient.discovery",
        "--hidden-import", "googleapiclient.http",
        # Audio
        "--hidden-import", "sounddevice",
        "--hidden-import", "numpy",
        "--collect-submodules", "numpy",
        "--hidden-import", "_sounddevice_data",
        # SSL certificates
        "--hidden-import", "certifi",
        "--collect-data", "certifi",
        # Stdlib dynamic imports (inside functions, PyInstaller may miss)
        "--hidden-import", "tarfile",
        "--hidden-import", "zipfile",
        "--hidden-import", "wave",
        # PDF export
        "--hidden-import", "reportlab",
        "--hidden-import", "reportlab.lib.pagesizes",
        "--hidden-import", "reportlab.pdfgen",
        "--hidden-import", "reportlab.pdfgen.canvas",
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

    print()
    print("=" * 50)
    print("BUILD COMPLETATA!")
    print("=" * 50)
    print(f"Cartella: {dist_app}")
    print()
    print("Copia la cartella dist/MyNotes/ su una chiavetta USB.")
    print()
    if sys.platform == "win32":
        print("Per avviare: doppio click su MyNotes.exe")
    else:
        print("Per avviare: ./MyNotes o doppio click su MyNotes")
    print()


if __name__ == "__main__":
    build()
