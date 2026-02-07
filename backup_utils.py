"""Sistema di backup locale e Google Drive - tutto configurabile da GUI."""

import os
import json
import shutil
import hashlib
import sqlite3
import logging
import threading
from datetime import datetime, timedelta
import database as db

log = logging.getLogger("backup")

SETTINGS_PATH = os.path.join(db.DATA_DIR, "backup_settings.json")
TOKEN_PATH = os.path.join(db.DATA_DIR, "gdrive_token.json")

# OAuth credentials integrati nell'app.
# Il developer li genera UNA volta su Google Cloud Console e li mette qui.
# Gli utenti NON devono fare nulla - cliccano solo "Accedi con Google".
OAUTH_CLIENT_CONFIG = {
    "installed": {
        "client_id": os.environ.get("MYNOTES_OAUTH_CLIENT_ID", ""),
        "client_secret": os.environ.get("MYNOTES_OAUTH_CLIENT_SECRET", ""),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_settings():
    defaults = {
        "auto_backup": True,
        "local_backup_dir": db.BACKUP_DIR,
        "gdrive_enabled": False,
        "gdrive_folder_name": "MyNotes Backup",
        "max_local_backups": 10,
        "retention_days": 90,
        "max_gdrive_backups": 20,
        "encrypt_backups": False,
        "backup_interval_minutes": 0,
        "last_backup_time": "",
    }
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r") as f:
                saved = json.load(f)
                defaults.update(saved)
        except (json.JSONDecodeError, OSError):
            pass
    return defaults


def save_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


BACKUP_KEY_PATH = os.path.join(db.DATA_DIR, "backup_key.json")
PRE_RESTORE_DIR = os.path.join(db.BACKUP_DIR, "pre_restore")


# --- Integrity & Checksum ---

def verify_backup_integrity(backup_path):
    """Esegue PRAGMA integrity_check su un backup .db. Ritorna (bool, msg)."""
    try:
        conn = sqlite3.connect(backup_path)
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        if result and result[0] == "ok":
            return True, "Integrita' OK"
        return False, f"Integrita' fallita: {result[0] if result else 'nessun risultato'}"
    except Exception as e:
        return False, f"Errore verifica: {e}"


def compute_checksum(file_path):
    """Calcola SHA-256 hex di un file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def save_checksum(backup_path):
    """Scrive file .sha256 sidecar accanto al backup."""
    checksum = compute_checksum(backup_path)
    sidecar = backup_path + ".sha256"
    with open(sidecar, "w") as f:
        f.write(checksum)
    return sidecar


def verify_checksum(backup_path):
    """Confronta checksum sidecar con file attuale. Ritorna (bool/None, msg).
    None indica checksum non disponibile (backup pre-feature).
    """
    sidecar = backup_path + ".sha256"
    if not os.path.exists(sidecar):
        return None, "Non disponibile"
    with open(sidecar, "r") as f:
        saved = f.read().strip()
    current = compute_checksum(backup_path)
    if saved == current:
        return True, "Checksum OK"
    return False, "Checksum non corrisponde: file modificato o corrotto"


def get_note_count_from_backup(path):
    """Apre un backup db e conta le note non cancellate."""
    try:
        conn = sqlite3.connect(path)
        row = conn.execute("SELECT COUNT(*) FROM notes WHERE is_deleted = 0").fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception:
        return -1


# --- Backup Encryption Helpers ---

def _get_backup_password():
    """Legge la password di crittografia backup dal file key."""
    if not os.path.exists(BACKUP_KEY_PATH):
        return None
    try:
        with open(BACKUP_KEY_PATH, "r") as f:
            data = json.load(f)
        return data.get("password")
    except (json.JSONDecodeError, OSError):
        return None


def set_backup_password(password):
    """Salva la password di crittografia backup."""
    os.makedirs(os.path.dirname(BACKUP_KEY_PATH), exist_ok=True)
    with open(BACKUP_KEY_PATH, "w") as f:
        json.dump({"password": password}, f)


def clear_backup_password():
    """Rimuove la password di crittografia backup."""
    if os.path.exists(BACKUP_KEY_PATH):
        os.remove(BACKUP_KEY_PATH)


# --- Restore ---

def restore_from_backup(path, password=None):
    """Ripristina un backup. Crea safety backup prima.
    Ritorna (success, message, safety_path).
    """
    try:
        # Safety backup
        os.makedirs(PRE_RESTORE_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safety_path = os.path.join(PRE_RESTORE_DIR, f"pre_restore_{ts}.db")
        if os.path.exists(db.DB_PATH):
            shutil.copy2(db.DB_PATH, safety_path)

        source = path
        temp_decrypted = None

        # Se file crittografato, decritta in temp
        if path.endswith(".db.enc"):
            if not password:
                return False, "Password richiesta per backup crittografato", safety_path
            import crypto_utils
            temp_decrypted = path + ".tmp"
            ok = crypto_utils.decrypt_file(path, temp_decrypted, password)
            if not ok:
                if os.path.exists(temp_decrypted):
                    os.remove(temp_decrypted)
                return False, "Decrittografia fallita: password errata?", safety_path
            source = temp_decrypted

        # Verifica integrita' prima del ripristino
        ok, msg = verify_backup_integrity(source)
        if not ok:
            if temp_decrypted and os.path.exists(temp_decrypted):
                os.remove(temp_decrypted)
            return False, f"Backup corrotto: {msg}", safety_path

        # Copia su DB principale
        shutil.copy2(source, db.DB_PATH)

        if temp_decrypted and os.path.exists(temp_decrypted):
            os.remove(temp_decrypted)

        log.info("Backup ripristinato da %s (safety: %s)", path, safety_path)
        return True, "Backup ripristinato con successo", safety_path

    except Exception as e:
        log.warning("Ripristino fallito: %s", e)
        return False, f"Errore ripristino: {e}", None


def is_gdrive_configured():
    """Check if Google Drive is authorized (token exists)."""
    return os.path.exists(TOKEN_PATH)


def is_gdrive_available():
    """Check if Google API libraries are installed."""
    try:
        import google.oauth2.credentials
        import google_auth_oauthlib.flow
        import googleapiclient.discovery
        return True
    except ImportError:
        return False


def gdrive_authorize():
    """
    Start Google Drive OAuth flow. Opens browser for user to authorize.
    Returns (success, message).
    """
    if not is_gdrive_available():
        return False, ("Librerie Google non installate.\n"
                       "Esegui nel terminale:\n"
                       "pip install google-api-python-client google-auth-oauthlib")

    if not OAUTH_CLIENT_CONFIG["installed"]["client_id"]:
        return False, ("OAuth non configurato dal developer.\n"
                       "Il developer deve inserire client_id e client_secret\n"
                       "in backup_utils.py > OAUTH_CLIENT_CONFIG")

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_config(OAUTH_CLIENT_CONFIG, SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")

        os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

        return True, "Google Drive autorizzato con successo!"

    except Exception as e:
        return False, f"Errore durante l'autorizzazione:\n{e}"


def gdrive_disconnect():
    """Remove Google Drive authorization."""
    if os.path.exists(TOKEN_PATH):
        os.remove(TOKEN_PATH)
    settings = get_settings()
    settings["gdrive_enabled"] = False
    save_settings(settings)


def _get_gdrive_service():
    """Get authenticated Google Drive service."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GRequest
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GRequest())
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def _get_or_create_folder(service, folder_name):
    """Get or create a folder on Google Drive. Returns folder ID."""
    results = service.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        spaces="drive", fields="files(id, name)", pageSize=1
    ).execute()

    files = results.get("files", [])
    if files:
        return files[0]["id"]

    folder_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    folder = service.files().create(body=folder_metadata, fields="id").execute()
    return folder["id"]


# --- Local Backup ---

def do_local_backup():
    settings = get_settings()
    dest = settings.get("local_backup_dir", db.BACKUP_DIR)
    backup_path = db.create_backup(dest)

    # Verifica integrita'
    ok, msg = verify_backup_integrity(backup_path)
    if not ok:
        log.warning("Integrita' backup fallita: %s", msg)

    # Salva checksum sidecar
    save_checksum(backup_path)

    # Crittografia se abilitata
    if settings.get("encrypt_backups"):
        password = _get_backup_password()
        if password:
            try:
                import crypto_utils
                enc_path = backup_path + ".enc"
                crypto_utils.encrypt_file(backup_path, enc_path, password)
                os.remove(backup_path)
                # Aggiorna sidecar per file crittografato
                os.remove(backup_path + ".sha256")
                save_checksum(enc_path)
                backup_path = enc_path
                log.info("Backup crittografato: %s", backup_path)
            except Exception as e:
                log.warning("Crittografia backup fallita: %s", e)

    max_backups = settings.get("max_local_backups", 10)
    retention_days = settings.get("retention_days", 90)
    _cleanup_old_backups(dest, max_backups, retention_days)

    # Aggiorna last_backup_time
    settings["last_backup_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_settings(settings)

    log.info("Backup creato: %s", backup_path)
    return backup_path


def _cleanup_old_backups(backup_dir, max_count, retention_days=0):
    if not os.path.exists(backup_dir):
        return
    backups = sorted(
        [f for f in os.listdir(backup_dir)
         if f.startswith("mynotes_backup_") and (f.endswith(".db") or f.endswith(".db.enc"))]
    )
    # Prima cancella per eta
    if retention_days > 0:
        cutoff = datetime.now() - timedelta(days=retention_days)
        expired = []
        for f in backups:
            try:
                # Rimuovi suffisso per parsing data
                name = f.replace(".db.enc", ".db")
                ts = datetime.strptime(name, "mynotes_backup_%Y%m%d_%H%M%S.db")
                if ts < cutoff:
                    expired.append(f)
            except ValueError:
                continue
        for f in expired:
            _remove_backup_file(backup_dir, f)
            backups.remove(f)
    # Poi applica limite per numero
    while len(backups) > max_count:
        old = backups.pop(0)
        _remove_backup_file(backup_dir, old)


def _remove_backup_file(backup_dir, filename):
    """Rimuove un file backup e il suo sidecar .sha256."""
    path = os.path.join(backup_dir, filename)
    if os.path.exists(path):
        os.remove(path)
    sidecar = path + ".sha256"
    if os.path.exists(sidecar):
        os.remove(sidecar)


# --- Google Drive Backup ---

def _cleanup_old_gdrive_backups(service, folder_id, max_count, retention_days):
    """Cancella backup vecchi su Google Drive: prima per eta, poi per numero."""
    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        spaces="drive",
        fields="files(id, name, createdTime)",
        orderBy="createdTime asc",
        pageSize=1000,
    ).execute()
    files = results.get("files", [])
    if not files:
        return
    # Prima cancella per eta
    if retention_days > 0:
        cutoff = datetime.now() - timedelta(days=retention_days)
        expired = []
        for f in files:
            try:
                ct = datetime.strptime(f["createdTime"], "%Y-%m-%dT%H:%M:%S.%fZ")
            except ValueError:
                continue
            if ct < cutoff:
                expired.append(f)
        for f in expired:
            service.files().delete(fileId=f["id"]).execute()
            files.remove(f)
    # Poi applica limite per numero
    if max_count > 0:
        while len(files) > max_count:
            old = files.pop(0)
            service.files().delete(fileId=old["id"]).execute()


def do_gdrive_backup(callback=None):
    """Upload backup to Google Drive in background thread."""
    def _upload():
        try:
            if not is_gdrive_configured():
                if callback:
                    callback(False, "Google Drive non autorizzato.\nVai in Backup > Impostazioni per configurarlo.")
                return

            backup_path = do_local_backup()
            backup_name = os.path.basename(backup_path)

            service = _get_gdrive_service()

            settings = get_settings()
            folder_name = settings.get("gdrive_folder_name", "MyNotes Backup")
            folder_id = _get_or_create_folder(service, folder_name)

            from googleapiclient.http import MediaFileUpload
            file_metadata = {"name": backup_name, "parents": [folder_id]}
            media = MediaFileUpload(backup_path, mimetype="application/octet-stream")
            service.files().create(body=file_metadata, media_body=media, fields="id").execute()

            # Cleanup vecchi backup su Google Drive
            retention_days = settings.get("retention_days", 90)
            max_gdrive = settings.get("max_gdrive_backups", 20)
            _cleanup_old_gdrive_backups(service, folder_id, max_gdrive, retention_days)

            log.info("Backup caricato su Google Drive: %s/%s", folder_name, backup_name)
            if callback:
                callback(True, f"Backup caricato su Google Drive\nCartella: {folder_name}\nFile: {backup_name}")

        except Exception as e:
            log.warning("Upload Google Drive fallito: %s", e)
            if callback:
                callback(False, f"Errore upload:\n{e}")

    threading.Thread(target=_upload, daemon=True).start()


def do_full_backup(callback=None):
    """Local backup + optional Google Drive."""
    backup_path = do_local_backup()
    settings = get_settings()

    if settings.get("gdrive_enabled") and is_gdrive_configured():
        def _cb(success, msg):
            if callback:
                callback(success, f"Backup locale: {backup_path}\n{msg}")
        do_gdrive_backup(_cb)
    else:
        if callback:
            callback(True, f"Backup locale creato:\n{backup_path}")


# --- Backup Scheduler ---

class BackupScheduler:
    """Scheduler per backup automatici basato su QTimer."""

    def __init__(self, parent):
        from PySide6.QtCore import QTimer
        self._timer = QTimer(parent)
        self._timer.timeout.connect(self._tick)
        self._interval_ms = 0

    def start(self):
        """Legge intervallo da settings e schedula il prossimo backup."""
        self.stop()
        settings = get_settings()
        minutes = settings.get("backup_interval_minutes", 0)
        if minutes <= 0:
            return
        self._interval_ms = minutes * 60 * 1000
        self._timer.start(self._interval_ms)
        log.info("Scheduler avviato: ogni %d minuti", minutes)

    def stop(self):
        """Cancella il timer schedulato."""
        self._timer.stop()

    def _tick(self):
        """Esegue backup in thread."""
        def _run():
            try:
                do_local_backup()
                settings = get_settings()
                if settings.get("gdrive_enabled") and is_gdrive_configured():
                    do_gdrive_backup()
                log.info("Scheduler: backup completato")
            except Exception as e:
                log.warning("Scheduler: backup fallito: %s", e)

        threading.Thread(target=_run, daemon=True).start()

    def restart_if_settings_changed(self):
        """Riavvia lo scheduler con le nuove impostazioni."""
        self.start()
