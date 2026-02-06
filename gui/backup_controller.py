"""Backup local and Google Drive."""

from tkinter import messagebox
import backup_utils
from dialogs import BackupSettingsDialog


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

    def open_settings(self):
        BackupSettingsDialog(self.app.root)
