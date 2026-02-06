"""Auto-update from GitHub Releases."""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import updater
from version import VERSION


class UpdateController:
    def __init__(self, app):
        self.app = app

    def check_silent(self):
        def _check():
            result = updater.check_for_updates()
            if result:
                self.app.root.after(0, lambda: self.app.status_var.set(
                    f"Aggiornamento disponibile: {result[0]} (Aiuto > Controlla aggiornamenti)"))
        threading.Thread(target=_check, daemon=True).start()

    def check(self):
        self.app.status_var.set("Controllo aggiornamenti...")
        def _check():
            result = updater.check_for_updates()
            self.app.root.after(0, lambda: self._handle_result(result))
        threading.Thread(target=_check, daemon=True).start()

    def _handle_result(self, result):
        if result is None:
            self.app.status_var.set("Nessun aggiornamento")
            messagebox.showinfo("Aggiornamenti", f"MyNotes v{VERSION} e' aggiornato!")
            return
        tag, url, notes = result
        msg = f"Nuova versione: {tag}\n(Attuale: v{VERSION})\n\nAggiornare?"
        if messagebox.askyesno("Aggiornamento", msg):
            self._do_update(url)

    def _do_update(self, download_url):
        app = self.app
        progress_win = tk.Toplevel(app.root)
        progress_win.title("Aggiornamento")
        progress_win.geometry("400x100")
        progress_win.resizable(False, False)
        progress_win.grab_set()
        progress_win.transient(app.root)
        frame = ttk.Frame(progress_win, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        status_label = ttk.Label(frame, text="Preparazione...")
        status_label.pack(anchor=tk.W)
        progress_bar = ttk.Progressbar(frame, mode="determinate", maximum=100)
        progress_bar.pack(fill=tk.X, pady=(10, 0))

        def on_progress(pct, msg):
            app.root.after(0, lambda: (status_label.config(text=msg),
                                       progress_bar.__setitem__("value", max(0, pct))))

        def do_download():
            success = updater.download_and_apply_update(download_url, on_progress)
            def finish():
                progress_win.destroy()
                if success:
                    if messagebox.askyesno("Completato", "Aggiornamento applicato!\nRiavviare ora?"):
                        import subprocess
                        subprocess.Popen(updater.get_restart_command())
                        app.root.quit()
                else:
                    messagebox.showerror("Errore", "Aggiornamento fallito.")
            app.root.after(0, finish)

        threading.Thread(target=do_download, daemon=True).start()
