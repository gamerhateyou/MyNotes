"""Backup local and Google Drive."""

import subprocess
from tkinter import messagebox
import backup_utils
import updater
from dialogs import BackupSettingsDialog, BackupRestoreDialog


class BackupController:
    def __init__(self, app):
        self.app = app

    def do_backup(self):
        try:
            path = backup_utils.do_local_backup()
            self.app.status_var.set(f"Backup creato: {path.split('/')[-1]}")
            messagebox.showinfo("Backup", f"Backup salvato:\n{path}")
        except Exception as e:
            messagebox.showerror("Errore", f"Backup fallito: {e}")

    def do_gdrive_backup(self):
        self.app.status_var.set("Upload Google Drive in corso...")

        def callback(success, msg):
            self.app.root.after(0, lambda: self._gdrive_result(success, msg))

        backup_utils.do_gdrive_backup(callback)

    def _gdrive_result(self, success, msg):
        if success:
            self.app.status_var.set("Backup Google Drive completato")
            messagebox.showinfo("Google Drive", msg)
        else:
            self.app.status_var.set("Backup Google Drive fallito")
            messagebox.showwarning("Google Drive", msg)

    def do_restore(self):
        dlg = BackupRestoreDialog(self.app.root)
        if not dlg.result:
            return

        path = dlg.result["path"]
        password = dlg.result.get("password")

        success, msg, safety_path = backup_utils.restore_from_backup(path, password)
        if success:
            info = f"{msg}\n\nBackup di sicurezza: {safety_path}\n\nL'app verra' riavviata."
            messagebox.showinfo("Ripristino completato", info)
            try:
                subprocess.Popen(updater.get_restart_command())
            except Exception:
                pass
            self.app.root.quit()
        else:
            messagebox.showerror("Errore ripristino", msg)

    def open_settings(self):
        BackupSettingsDialog(self.app.root)
        # Restart scheduler se impostazioni cambiate
        if hasattr(self.app, '_backup_scheduler'):
            self.app._backup_scheduler.restart_if_settings_changed()
