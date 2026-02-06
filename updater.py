"""Sistema di auto-aggiornamento da GitHub Releases."""

import json
import os
import sys
import shutil
import tempfile
import platform
import threading
from urllib.request import urlopen, Request
from urllib.error import URLError

from version import VERSION, GITHUB_REPO

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _parse_version(v):
    """Converte 'v1.2.3' o '1.2.3' in tupla (1, 2, 3)."""
    v = v.lstrip("v").strip()
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def check_for_updates():
    """
    Controlla se esiste una versione più recente su GitHub.
    Ritorna (new_version, download_url, release_notes) oppure None.
    """
    if not GITHUB_REPO:
        return None

    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = Request(url, headers={"Accept": "application/vnd.github.v3+json"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except (URLError, json.JSONDecodeError, OSError):
        return None

    tag = data.get("tag_name", "")
    remote_ver = _parse_version(tag)
    local_ver = _parse_version(VERSION)

    if remote_ver <= local_ver:
        return None

    # Trova l'asset giusto per questa piattaforma
    is_windows = sys.platform == "win32"
    target = "Windows" if is_windows else "Linux"

    download_url = None
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if target in name:
            download_url = asset.get("browser_download_url")
            break

    if not download_url:
        return None

    notes = data.get("body", "")
    return (tag, download_url, notes)


def download_and_apply_update(download_url, progress_callback=None):
    """
    Scarica l'aggiornamento e lo applica.
    progress_callback(percentage, message) viene chiamato durante il download.
    Ritorna True se l'aggiornamento è stato applicato e serve un riavvio.
    """
    is_windows = sys.platform == "win32"
    tmp_dir = tempfile.mkdtemp(prefix="mynotes_update_")

    try:
        # Download
        if progress_callback:
            progress_callback(0, "Download in corso...")

        archive_name = "update.zip" if is_windows else "update.tar.gz"
        archive_path = os.path.join(tmp_dir, archive_name)

        req = Request(download_url)
        with urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 65536

            with open(archive_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total > 0:
                        pct = int(downloaded * 100 / total)
                        progress_callback(pct, f"Download: {downloaded // 1024} / {total // 1024} KB")

        if progress_callback:
            progress_callback(100, "Estrazione archivio...")

        # Estrai
        extract_dir = os.path.join(tmp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)

        if archive_path.endswith(".zip"):
            import zipfile
            with zipfile.ZipFile(archive_path, 'r') as z:
                z.extractall(extract_dir)
        else:
            import tarfile
            with tarfile.open(archive_path, 'r:gz') as t:
                t.extractall(extract_dir)

        # Trova la cartella estratta (potrebbe essere MyNotes/ dentro l'archivio)
        extracted_contents = os.listdir(extract_dir)
        if len(extracted_contents) == 1 and os.path.isdir(os.path.join(extract_dir, extracted_contents[0])):
            source_dir = os.path.join(extract_dir, extracted_contents[0])
        else:
            source_dir = extract_dir

        if progress_callback:
            progress_callback(100, "Applicazione aggiornamento...")

        # Applica: copia tutti i file TRANNE data/
        if is_windows:
            # Su Windows non possiamo sovrascrivere l'exe in uso.
            # Creiamo uno script .bat che fa il lavoro dopo la chiusura.
            _create_windows_update_script(source_dir, APP_DIR, tmp_dir)
        else:
            _apply_files(source_dir, APP_DIR)
            # Pulizia
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return True

    except Exception as e:
        if progress_callback:
            progress_callback(-1, f"Errore: {e}")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return False


def _apply_files(source_dir, dest_dir):
    """Copia i file aggiornati preservando data/."""
    for item in os.listdir(source_dir):
        if item == "data":
            continue  # MAI sovrascrivere i dati utente
        src = os.path.join(source_dir, item)
        dst = os.path.join(dest_dir, item)

        if os.path.isdir(src):
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)


def _create_windows_update_script(source_dir, app_dir, tmp_dir):
    """Crea un .bat che aggiorna l'app dopo la chiusura su Windows."""
    bat_path = os.path.join(tmp_dir, "update.bat")

    # Trova l'eseguibile
    exe_name = "MyNotes.exe"
    exe_path = os.path.join(app_dir, exe_name)

    with open(bat_path, "w") as f:
        f.write("@echo off\n")
        f.write("echo Aggiornamento MyNotes in corso...\n")
        f.write("timeout /t 3 /nobreak >nul\n")  # attendi chiusura app
        # Copia file (non data/)
        for item in os.listdir(source_dir):
            if item == "data":
                continue
            src = os.path.join(source_dir, item).replace("/", "\\")
            dst = os.path.join(app_dir, item).replace("/", "\\")
            if os.path.isdir(os.path.join(source_dir, item)):
                f.write(f'rmdir /s /q "{dst}" 2>nul\n')
                f.write(f'xcopy /e /i /y "{src}" "{dst}"\n')
            else:
                f.write(f'copy /y "{src}" "{dst}"\n')
        f.write("echo Aggiornamento completato!\n")
        # Riavvia l'app
        f.write(f'start "" "{exe_path}"\n')
        # Auto-pulizia
        f.write(f'rmdir /s /q "{tmp_dir.replace("/", chr(92))}"\n')
        f.write("exit\n")

    # Lancia lo script in background
    import subprocess
    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=0x00000008,  # DETACHED_PROCESS
        close_fds=True
    )


def get_restart_command():
    """Ritorna il comando per riavviare l'app."""
    if getattr(sys, 'frozen', False):
        return [sys.executable]
    else:
        return [sys.executable] + sys.argv
