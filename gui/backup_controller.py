"""Backup local and Google Drive (PySide6)."""

import subprocess
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QTimer
import backup_utils
import updater
from dialogs import BackupSettingsDialog, BackupRestoreDialog


class BackupController:
    def __init__(self, app):
        self.app = app

    def do_backup(self):
        try:
            path = backup_utils.do_local_backup()
            self.app.statusBar().showMessage(f"Backup creato: {path.split('/')[-1]}")
            QMessageBox.information(self.app, "Backup", f"Backup salvato:\n{path}")
        except Exception as e:
            QMessageBox.critical(self.app, "Errore", f"Backup fallito: {e}")

    def do_gdrive_backup(self):
        self.app.statusBar().showMessage("Upload Google Drive in corso...")

        def callback(success, msg):
            QTimer.singleShot(0, lambda: self._gdrive_result(success, msg))

        backup_utils.do_gdrive_backup(callback)

    def _gdrive_result(self, success, msg):
        if success:
            self.app.statusBar().showMessage("Backup Google Drive completato")
            QMessageBox.information(self.app, "Google Drive", msg)
        else:
            self.app.statusBar().showMessage("Backup Google Drive fallito")
            QMessageBox.warning(self.app, "Google Drive", msg)

    def do_restore(self):
        dlg = BackupRestoreDialog(self.app)
        if not dlg.result:
            return

        path = dlg.result["path"]
        password = dlg.result.get("password")

        success, msg, safety_path = backup_utils.restore_from_backup(path, password)
        if success:
            info = f"{msg}\n\nBackup di sicurezza: {safety_path}\n\nL'app verra' riavviata."
            QMessageBox.information(self.app, "Ripristino completato", info)
            try:
                subprocess.Popen(updater.get_restart_command())
            except Exception:
                pass
            self.app.close()
        else:
            QMessageBox.critical(self.app, "Errore ripristino", msg)

    def open_settings(self):
        BackupSettingsDialog(self.app)
        if hasattr(self.app, '_backup_scheduler'):
            self.app._backup_scheduler.restart_if_settings_changed()
