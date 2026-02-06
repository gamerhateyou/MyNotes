"""Sistema di backup locale e Google Drive - tutto configurabile da GUI."""

import os
import json
import shutil
import threading
from datetime import datetime, timedelta
import database as db

SETTINGS_PATH = os.path.join(db.DATA_DIR, "backup_settings.json")
TOKEN_PATH = os.path.join(db.DATA_DIR, "gdrive_token.json")

# OAuth credentials integrati nell'app.
# Il developer li genera UNA volta su Google Cloud Console e li mette qui.
# Gli utenti NON devono fare nulla - cliccano solo "Accedi con Google".
OAUTH_CLIENT_CONFIG = {
    "installed": {
        "client_id": "",
        "client_secret": "",
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
    max_backups = settings.get("max_local_backups", 10)
    retention_days = settings.get("retention_days", 90)
    _cleanup_old_backups(dest, max_backups, retention_days)
    return backup_path


def _cleanup_old_backups(backup_dir, max_count, retention_days=0):
    if not os.path.exists(backup_dir):
        return
    backups = sorted(
        [f for f in os.listdir(backup_dir) if f.startswith("mynotes_backup_") and f.endswith(".db")]
    )
    # Prima cancella per eta
    if retention_days > 0:
        cutoff = datetime.now() - timedelta(days=retention_days)
        expired = []
        for f in backups:
            try:
                ts = datetime.strptime(f, "mynotes_backup_%Y%m%d_%H%M%S.db")
                if ts < cutoff:
                    expired.append(f)
            except ValueError:
                continue
        for f in expired:
            os.remove(os.path.join(backup_dir, f))
            backups.remove(f)
    # Poi applica limite per numero
    while len(backups) > max_count:
        old = backups.pop(0)
        os.remove(os.path.join(backup_dir, old))


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

            if callback:
                callback(True, f"Backup caricato su Google Drive\nCartella: {folder_name}\nFile: {backup_name}")

        except Exception as e:
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
