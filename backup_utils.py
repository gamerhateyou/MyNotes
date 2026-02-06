"""Sistema di backup locale e Google Drive."""

import os
import json
import shutil
import threading
from datetime import datetime
import database as db


SETTINGS_PATH = os.path.join(db.DATA_DIR, "backup_settings.json")


def get_settings():
    """Load backup settings."""
    defaults = {
        "auto_backup": True,
        "local_backup_dir": db.BACKUP_DIR,
        "gdrive_enabled": False,
        "gdrive_folder_id": "",
        "max_local_backups": 10,
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
    """Save backup settings."""
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


def do_local_backup():
    """Create a local backup and clean up old ones."""
    settings = get_settings()
    dest = settings.get("local_backup_dir", db.BACKUP_DIR)
    backup_path = db.create_backup(dest)
    # Cleanup old backups
    max_backups = settings.get("max_local_backups", 10)
    _cleanup_old_backups(dest, max_backups)
    return backup_path


def _cleanup_old_backups(backup_dir, max_count):
    """Keep only the most recent N backups."""
    if not os.path.exists(backup_dir):
        return
    backups = sorted(
        [f for f in os.listdir(backup_dir) if f.startswith("mynotes_backup_") and f.endswith(".db")]
    )
    while len(backups) > max_count:
        old = backups.pop(0)
        os.remove(os.path.join(backup_dir, old))


def do_gdrive_backup(callback=None):
    """
    Upload backup to Google Drive.
    callback(success, message) is called when done.
    Requires google-api-python-client and google-auth-oauthlib.
    """
    settings = get_settings()
    if not settings.get("gdrive_enabled"):
        if callback:
            callback(False, "Google Drive non abilitato.")
        return

    def _upload():
        try:
            # Create local backup first
            backup_path = do_local_backup()
            backup_name = os.path.basename(backup_path)

            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request as GRequest
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            creds_path = os.path.join(db.DATA_DIR, "gdrive_credentials.json")
            token_path = os.path.join(db.DATA_DIR, "gdrive_token.json")

            SCOPES = ['https://www.googleapis.com/auth/drive.file']

            creds = None
            if os.path.exists(token_path):
                creds = Credentials.from_authorized_user_file(token_path, SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(GRequest())
                else:
                    if not os.path.exists(creds_path):
                        if callback:
                            callback(False,
                                     "File gdrive_credentials.json non trovato in data/.\n"
                                     "Scaricalo da Google Cloud Console > API > Credentials > OAuth 2.0.")
                        return
                    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                    creds = flow.run_local_server(port=0)

                with open(token_path, 'w') as token:
                    token.write(creds.to_json())

            service = build('drive', 'v3', credentials=creds)

            file_metadata = {'name': backup_name}
            folder_id = settings.get("gdrive_folder_id")
            if folder_id:
                file_metadata['parents'] = [folder_id]

            media = MediaFileUpload(backup_path, mimetype='application/octet-stream')
            service.files().create(body=file_metadata, media_body=media, fields='id').execute()

            if callback:
                callback(True, f"Backup caricato su Google Drive: {backup_name}")

        except ImportError:
            if callback:
                callback(False,
                         "Librerie Google Drive non installate.\n"
                         "Esegui: pip install google-api-python-client google-auth-oauthlib")
        except Exception as e:
            if callback:
                callback(False, f"Errore upload Google Drive: {e}")

    threading.Thread(target=_upload, daemon=True).start()


def do_full_backup(callback=None):
    """Create local backup + optional Google Drive upload."""
    backup_path = do_local_backup()
    settings = get_settings()

    if settings.get("gdrive_enabled"):
        def _gdrive_callback(success, msg):
            if callback:
                callback(success, f"Backup locale: {backup_path}\n{msg}")
        do_gdrive_backup(_gdrive_callback)
    else:
        if callback:
            callback(True, f"Backup locale creato: {backup_path}")
