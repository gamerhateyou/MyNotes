"""Backup local and Google Drive (PySide6)."""

from __future__ import annotations

import contextlib
import logging
import subprocess
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

import backup_utils
import updater
from dialogs import BackupLogDialog, BackupRestoreDialog, BackupSettingsDialog

if TYPE_CHECKING:
    from gui import MyNotesApp

log: logging.Logger = logging.getLogger("backup")


class BackupController:
    def __init__(self, app: MyNotesApp) -> None:
        self.app = app

    def do_backup(self) -> None:
        log.info("Backup locale richiesto dall'utente")
        try:
            path = backup_utils.do_local_backup()
            self.app.statusBar().showMessage(f"Backup creato: {path.split('/')[-1]}")
            QMessageBox.information(self.app, "Backup", f"Backup salvato:\n{path}")
        except Exception as e:
            log.warning("Backup locale fallito: %s", e)
            QMessageBox.critical(self.app, "Errore", f"Backup fallito: {e}")

    def do_gdrive_backup(self) -> None:
        log.info("Backup Google Drive richiesto dall'utente")
        self.app.statusBar().showMessage("Upload Google Drive in corso...")

        def callback(success: bool, msg: str) -> None:
            QTimer.singleShot(0, lambda: self._gdrive_result(success, msg))

        backup_utils.do_gdrive_backup(callback)

    def _gdrive_result(self, success: bool, msg: str) -> None:
        if success:
            self.app.statusBar().showMessage("Backup Google Drive completato")
            QMessageBox.information(self.app, "Google Drive", msg)
        else:
            self.app.statusBar().showMessage("Backup Google Drive fallito")
            QMessageBox.warning(self.app, "Google Drive", msg)

    def do_restore(self) -> None:
        dlg = BackupRestoreDialog(self.app)
        if not dlg.result:
            return

        path = dlg.result["path"]
        password = dlg.result.get("password")

        success, msg, safety_path = backup_utils.restore_from_backup(path, password)
        if success:
            info = f"{msg}\n\nBackup di sicurezza: {safety_path}\n\nL'app verra' riavviata."
            QMessageBox.information(self.app, "Ripristino completato", info)
            with contextlib.suppress(Exception):
                subprocess.Popen(updater.get_restart_command())
            self.app.close()
        else:
            QMessageBox.critical(self.app, "Errore ripristino", msg)

    def show_backup_log(self) -> None:
        BackupLogDialog(self.app)

    def open_settings(self) -> None:
        BackupSettingsDialog(self.app)
        if hasattr(self.app, "_backup_scheduler"):
            self.app._backup_scheduler.restart_if_settings_changed()
