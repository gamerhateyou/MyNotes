"""Sistema di backup locale — configurabile da GUI. GDrive in gdrive_utils.py."""

import os
import json
import shutil
import hashlib
import sqlite3
import logging
import threading
from datetime import datetime, timedelta
import database as db

# Re-export GDrive functions for backward compatibility
from gdrive_utils import (is_gdrive_configured, is_gdrive_available,
                          gdrive_authorize, gdrive_disconnect,
                          do_gdrive_backup, list_gdrive_backups,
                          download_gdrive_backup)

log = logging.getLogger("backup")

SETTINGS_PATH = os.path.join(db.DATA_DIR, "backup_settings.json")


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
    db._secure_file(SETTINGS_PATH)


_LEGACY_KEY_PATH = os.path.join(db.DATA_DIR, "backup_key.json")
PRE_RESTORE_DIR = os.path.join(db.BACKUP_DIR, "pre_restore")

# --- Backup password: in-memory only (mai salvata su disco) ---
_session_password = None


def get_backup_password():
    """Ritorna la password di crittografia backup (solo in memoria)."""
    return _session_password


def set_backup_password(password):
    """Imposta la password di crittografia backup (solo in memoria)."""
    global _session_password
    _session_password = password


def clear_backup_password():
    """Cancella la password dalla memoria."""
    global _session_password
    _session_password = None


def migrate_legacy_password():
    """Migra password da backup_key.json (plaintext) a memoria, poi cancella il file."""
    global _session_password
    if not os.path.exists(_LEGACY_KEY_PATH):
        return False
    try:
        with open(_LEGACY_KEY_PATH, "r") as f:
            data = json.load(f)
        pw = data.get("password")
        if pw:
            _session_password = pw
            os.remove(_LEGACY_KEY_PATH)
            log.info("Password backup migrata in memoria (backup_key.json rimosso)")
            return True
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Migrazione password fallita: %s", e)
    return False


def has_backup_password():
    """Controlla se la password e' disponibile (in memoria)."""
    return _session_password is not None


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
            ok, err = crypto_utils.decrypt_file(path, temp_decrypted, password)
            if not ok:
                if os.path.exists(temp_decrypted):
                    os.remove(temp_decrypted)
                detail = f"\n({err})" if err else ""
                return False, f"Decrittografia fallita: password errata?{detail}", safety_path
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
        password = get_backup_password()
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
                settings = get_settings()
                if settings.get("encrypt_backups") and not has_backup_password():
                    log.warning("Scheduler: backup saltato — password crittografia non disponibile")
                    return
                do_local_backup()
                if settings.get("gdrive_enabled") and is_gdrive_configured():
                    do_gdrive_backup()
                log.info("Scheduler: backup completato")
            except Exception as e:
                log.warning("Scheduler: backup fallito: %s", e)

        threading.Thread(target=_run, daemon=True).start()

    def restart_if_settings_changed(self):
        """Riavvia lo scheduler con le nuove impostazioni."""
        self.start()
