"""Sistema di auto-aggiornamento da GitHub Releases."""

import json
import logging
import os
import sys
import shutil
import tempfile
import platform
import threading
from urllib.request import urlopen, Request
from urllib.error import URLError

import ssl
import certifi

from version import VERSION, GITHUB_REPO

log = logging.getLogger("updater")

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

SETTINGS_PATH = os.path.join(APP_DIR, "data", "update_settings.json")


def get_update_settings():
    """Ritorna le preferenze di aggiornamento con defaults."""
    defaults = {"auto_check": True, "skipped_versions": []}
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r") as f:
                saved = json.load(f)
                defaults.update(saved)
        except (json.JSONDecodeError, OSError):
            pass
    return defaults


def save_update_settings(settings):
    """Salva le preferenze di aggiornamento."""
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


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


def check_for_updates(skip_versions=None):
    """
    Controlla se esiste una versione più recente su GitHub.
    Ritorna (new_version, download_url, release_notes) oppure None.
    Lancia ConnectionError se non riesce a contattare GitHub.
    Se skip_versions è una lista, versioni in essa vengono ignorate.
    """
    log.info("Controllo aggiornamenti - versione locale: %s, repo: %s", VERSION, GITHUB_REPO)

    if not GITHUB_REPO:
        log.warning("GITHUB_REPO non configurato, skip")
        return None

    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    log.info("Richiesta API: %s", url)
    try:
        ctx = ssl.create_default_context(cafile=certifi.where())
        req = Request(url, headers={"Accept": "application/vnd.github.v3+json"})
        with urlopen(req, timeout=10, context=ctx) as resp:
            raw = resp.read().decode()
            data = json.loads(raw)
    except (URLError, json.JSONDecodeError, OSError) as e:
        log.error("Errore contatto GitHub: %s: %s", type(e).__name__, e)
        raise ConnectionError(f"Impossibile contattare GitHub: {e}")

    tag = data.get("tag_name", "")
    remote_ver = _parse_version(tag)
    local_ver = _parse_version(VERSION)
    log.info("Versione remota: %s %s, locale: %s %s", tag, remote_ver, VERSION, local_ver)

    if remote_ver <= local_ver:
        log.info("Nessun aggiornamento disponibile (remota <= locale)")
        return None

    if skip_versions and tag in skip_versions:
        log.info("Versione %s nella lista skip, ignorata", tag)
        return None

    # Trova l'asset giusto per questa piattaforma
    is_windows = sys.platform == "win32"
    target = "Windows" if is_windows else "Linux"
    asset_names = [a.get("name", "") for a in data.get("assets", [])]
    log.info("Piattaforma: %s, asset disponibili: %s", target, asset_names)

    download_url = None
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if target in name:
            download_url = asset.get("browser_download_url")
            break

    if not download_url:
        log.warning("Nessun asset trovato per piattaforma '%s'", target)
        return None

    notes = data.get("body", "")
    log.info("Aggiornamento disponibile: %s -> %s", download_url, tag)
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

        ctx = ssl.create_default_context(cafile=certifi.where())
        req = Request(download_url)
        with urlopen(req, timeout=120, context=ctx) as resp:
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
