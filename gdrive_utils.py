"""Google Drive backup integration — OAuth, upload, list, download."""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import database as db

log: logging.Logger = logging.getLogger("backup.gdrive")

TOKEN_PATH: str = os.path.join(db.DATA_DIR, "gdrive_token.json")

# OAuth credentials integrati nell'app.
# Il developer li genera UNA volta su Google Cloud Console e li mette qui.
# Gli utenti NON devono fare nulla - cliccano solo "Accedi con Google".
OAUTH_CLIENT_CONFIG: dict[str, Any] = {
    "installed": {
        "client_id": os.environ.get("MYNOTES_OAUTH_CLIENT_ID", ""),
        "client_secret": os.environ.get("MYNOTES_OAUTH_CLIENT_SECRET", ""),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}
SCOPES: list[str] = ["https://www.googleapis.com/auth/drive.file"]


def is_gdrive_configured() -> bool:
    """Check if Google Drive is authorized (token exists)."""
    return os.path.exists(TOKEN_PATH)


def is_gdrive_available() -> bool:
    """Check if Google API libraries are installed."""
    try:
        import google.oauth2.credentials  # noqa: F401
        import google_auth_oauthlib.flow  # noqa: F401
        import googleapiclient.discovery  # noqa: F401

        return True
    except ImportError:
        return False


def gdrive_authorize() -> tuple[bool, str]:
    """Start Google Drive OAuth flow. Opens browser for user to authorize.
    Returns (success, message).
    """
    if not is_gdrive_available():
        return False, (
            "Librerie Google non installate.\n"
            "Esegui nel terminale:\n"
            "pip install google-api-python-client google-auth-oauthlib"
        )

    if not OAUTH_CLIENT_CONFIG["installed"]["client_id"]:
        return False, (
            "OAuth non configurato dal developer.\n"
            "Il developer deve inserire client_id e client_secret\n"
            "in gdrive_utils.py > OAUTH_CLIENT_CONFIG"
        )

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_config(OAUTH_CLIENT_CONFIG, SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")

        os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        db._secure_file(TOKEN_PATH)

        return True, "Google Drive autorizzato con successo!"

    except Exception as e:
        return False, f"Errore durante l'autorizzazione:\n{e}"


def gdrive_disconnect() -> None:
    """Remove Google Drive authorization."""
    if os.path.exists(TOKEN_PATH):
        os.remove(TOKEN_PATH)
    from backup_utils import get_settings, save_settings

    settings = get_settings()
    settings["gdrive_enabled"] = False
    save_settings(settings)


def _get_gdrive_service() -> Any:
    """Get authenticated Google Drive service."""
    from google.auth.transport.requests import Request as GRequest
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)  # type: ignore[no-untyped-call]
    if creds.expired and creds.refresh_token:
        creds.refresh(GRequest())
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        db._secure_file(TOKEN_PATH)

    return build("drive", "v3", credentials=creds)


def _get_or_create_folder(service: Any, folder_name: str) -> str:
    """Get or create a folder on Google Drive. Returns folder ID."""
    results = (
        service.files()
        .list(
            q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            spaces="drive",
            fields="files(id, name)",
            pageSize=1,
        )
        .execute()
    )

    files = results.get("files", [])
    if files:
        return str(files[0]["id"])

    folder_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    folder = service.files().create(body=folder_metadata, fields="id").execute()
    return str(folder["id"])


def _cleanup_old_gdrive_backups(service: Any, folder_id: str, max_count: int, retention_days: int) -> None:
    """Cancella backup vecchi su Google Drive: prima per eta, poi per numero."""
    results = (
        service.files()
        .list(
            q=f"'{folder_id}' in parents and trashed=false",
            spaces="drive",
            fields="files(id, name, createdTime)",
            orderBy="createdTime asc",
            pageSize=1000,
        )
        .execute()
    )
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


def do_gdrive_backup(callback: Callable[[bool, str], None] | None = None) -> None:
    """Upload backup to Google Drive in background thread."""

    def _upload() -> None:
        try:
            if not is_gdrive_configured():
                if callback:
                    callback(False, "Google Drive non autorizzato.\nVai in Backup > Impostazioni per configurarlo.")
                return

            log.info("Avvio upload Google Drive")

            from backup_utils import do_local_backup, get_settings

            backup_path = do_local_backup()
            backup_name = os.path.basename(backup_path)
            log.info("Backup locale creato: %s", backup_name)

            service = _get_gdrive_service()
            log.info("Autenticazione Google Drive OK")

            settings = get_settings()
            folder_name = settings.get("gdrive_folder_name", "MyNotes Backup")
            folder_id = _get_or_create_folder(service, folder_name)
            log.info("Cartella Drive trovata: %s", folder_name)

            from googleapiclient.http import MediaFileUpload

            file_metadata = {"name": backup_name, "parents": [folder_id]}
            media = MediaFileUpload(backup_path, mimetype="application/octet-stream")
            log.info("Upload file in corso: %s", backup_name)
            service.files().create(body=file_metadata, media_body=media, fields="id").execute()

            # Cleanup vecchi backup su Google Drive
            retention_days = settings.get("retention_days", 90)
            max_gdrive = settings.get("max_gdrive_backups", 20)
            _cleanup_old_gdrive_backups(service, folder_id, max_gdrive, retention_days)
            log.info("Pulizia backup vecchi completata")

            log.info("Backup caricato su Google Drive: %s/%s", folder_name, backup_name)
            if callback:
                callback(True, f"Backup caricato su Google Drive\nCartella: {folder_name}\nFile: {backup_name}")

        except Exception as e:
            log.warning("Upload Google Drive fallito: %s", e)
            if callback:
                callback(False, f"Errore upload:\n{e}")

    threading.Thread(target=_upload, daemon=True).start()


def list_gdrive_backups() -> list[dict[str, Any]]:
    """Lista backup disponibili su Google Drive. Ritorna lista di dict."""
    if not is_gdrive_configured():
        return []
    try:
        from backup_utils import get_settings

        service = _get_gdrive_service()
        settings = get_settings()
        folder_name = settings.get("gdrive_folder_name", "MyNotes Backup")
        folder_id = _get_or_create_folder(service, folder_name)

        results = (
            service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed=false",
                spaces="drive",
                fields="files(id, name, size, createdTime)",
                orderBy="createdTime desc",
                pageSize=100,
            )
            .execute()
        )

        backups = []
        for f in results.get("files", []):
            name = f.get("name", "")
            if not (name.endswith(".db") or name.endswith(".db.enc")):
                continue
            try:
                ct = datetime.strptime(f["createdTime"], "%Y-%m-%dT%H:%M:%S.%fZ")
                date_str = ct.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, KeyError):
                date_str = "?"
            backups.append(
                {
                    "id": f["id"],
                    "name": name,
                    "size": int(f.get("size", 0)),
                    "date_str": date_str,
                    "encrypted": name.endswith(".db.enc"),
                }
            )
        return backups
    except Exception as e:
        log.warning("Errore lista backup GDrive: %s", e)
        return []


def download_gdrive_backup(file_id: str, dest_path: str) -> tuple[bool, str]:
    """Scarica un backup da Google Drive. Ritorna (success, message)."""
    try:
        service = _get_gdrive_service()
        from googleapiclient.http import MediaIoBaseDownload

        request = service.files().get_media(fileId=file_id)
        with open(dest_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        log.info("Backup GDrive scaricato: %s", dest_path)
        return True, "Download completato"
    except Exception as e:
        log.warning("Download backup GDrive fallito: %s", e)
        return False, f"Errore download: {e}"
