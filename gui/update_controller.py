"""Auto-update from GitHub Releases."""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import updater
from version import VERSION
from gui.constants import UI_FONT
from error_codes import AppError

log = logging.getLogger("updater.gui")


class UpdateController:
    def __init__(self, app):
        self.app = app

    def check_silent(self):
        settings = updater.get_update_settings()
        if not settings.get("auto_check", True):
            log.info("check_silent: auto_check disabilitato, skip")
            return

        skip = settings.get("skipped_versions", [])

        def _check():
            try:
                result = updater.check_for_updates(skip_versions=skip)
            except Exception:
                log.warning("check_silent: errore ignorato", exc_info=True)
                return
            if result:
                tag, url, notes = result
                self.app.root.after(0, lambda: self._show_update_available(tag, url, notes))

        threading.Thread(target=_check, daemon=True).start()

    def check(self):
        """Check manuale da menu: ignora skip e auto_check, riabilita se disabilitato."""
        log.info("check() avviato dall'utente")
        self.app.status_var.set("Controllo aggiornamenti...")

        # Riabilita auto_check e pulisci skip
        settings = updater.get_update_settings()
        if not settings.get("auto_check", True) or settings.get("skipped_versions"):
            settings["auto_check"] = True
            settings["skipped_versions"] = []
            updater.save_update_settings(settings)
            log.info("check(): riabilitato auto_check e pulito skipped_versions")

        def _check():
            try:
                result = updater.check_for_updates()
                log.info("check_for_updates() ritornato: %s", result)
                self.app.root.after(0, lambda: self._handle_result(result))
            except AppError as e:
                log.warning("Errore strutturato nel controllo: %s", e, exc_info=True)
                self.app.root.after(0, lambda: self._handle_error(e.code, e.message, e.detail))
            except Exception as e:
                log.error("Eccezione nel thread di controllo: %s: %s", type(e).__name__, e, exc_info=True)
                self.app.root.after(0, lambda: self._handle_error(None, str(e), ""))

        threading.Thread(target=_check, daemon=True).start()

    def _handle_error(self, code, message, detail):
        log.info("_handle_error: code=%s message=%s detail=%s", code, message, detail)
        if code:
            self.app.status_var.set(f"Errore: {code}")
            body = f"Impossibile verificare aggiornamenti.\n\nCodice errore: {code}\n{message}"
            if detail:
                body += f"\n\nDettaglio: {detail}"
            body += "\n\nFile di log: data/mynotes.log"
        else:
            self.app.status_var.set("Errore controllo aggiornamenti")
            body = f"Impossibile verificare aggiornamenti.\n\n{message}"
            body += "\n\nFile di log: data/mynotes.log"
        messagebox.showerror("Errore", body, parent=self.app.root)

    def _handle_result(self, result):
        log.info("_handle_result: %s", result)
        if result is None:
            self.app.status_var.set("Nessun aggiornamento")
            messagebox.showinfo("Aggiornamenti", f"MyNotes v{VERSION} e' aggiornato!",
                                parent=self.app.root)
            return
        tag, url, notes = result
        self._show_update_available(tag, url, notes)

    def _show_update_available(self, tag, url, notes):
        """Dialog con 3 opzioni: Aggiorna, Salta versione, Non ricordare."""
        dlg = tk.Toplevel(self.app.root)
        dlg.title("Aggiornamento disponibile")
        dlg.resizable(False, False)
        dlg.transient(self.app.root)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Nuova versione disponibile: {tag}",
                  font=(UI_FONT, 12, "bold")).pack(anchor=tk.W)
        ttk.Label(frame, text=f"Versione attuale: v{VERSION}",
                  font=(UI_FONT, 9), foreground="#666666").pack(anchor=tk.W, pady=(2, 10))

        if notes:
            notes_frame = ttk.LabelFrame(frame, text="Note di rilascio", padding=8)
            notes_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
            notes_text = tk.Text(notes_frame, wrap=tk.WORD, height=8, width=50,
                                 font=(UI_FONT, 9))
            notes_text.insert("1.0", notes)
            notes_text.config(state=tk.DISABLED)
            notes_text.pack(fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)

        def on_update():
            dlg.destroy()
            self._do_update(url)

        def on_skip():
            settings = updater.get_update_settings()
            skipped = settings.get("skipped_versions", [])
            if tag not in skipped:
                skipped.append(tag)
            settings["skipped_versions"] = skipped
            updater.save_update_settings(settings)
            log.info("Versione %s aggiunta a skipped_versions", tag)
            self.app.status_var.set(f"Versione {tag} saltata")
            dlg.destroy()

        def on_disable():
            settings = updater.get_update_settings()
            settings["auto_check"] = False
            updater.save_update_settings(settings)
            log.info("auto_check disabilitato dall'utente")
            self.app.status_var.set("Notifiche aggiornamenti disabilitate")
            dlg.destroy()

        ttk.Button(btn_frame, text="Aggiorna", command=on_update).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text=f"Salta {tag}", command=on_skip).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Non ricordare", command=on_disable).pack(side=tk.RIGHT)

        # Centra il dialog sulla finestra principale
        dlg.update_idletasks()
        w = dlg.winfo_width()
        h = dlg.winfo_height()
        x = self.app.root.winfo_x() + (self.app.root.winfo_width() - w) // 2
        y = self.app.root.winfo_y() + (self.app.root.winfo_height() - h) // 2
        dlg.geometry(f"+{x}+{y}")

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

        last_error = [None]

        def on_progress(pct, msg):
            if pct < 0:
                last_error[0] = msg
            app.root.after(0, lambda: (status_label.config(text=msg),
                                       progress_bar.__setitem__("value", max(0, pct))))

        def do_download():
            success = updater.download_and_apply_update(download_url, on_progress)
            def finish():
                progress_win.destroy()
                if success:
                    import sys
                    is_windows = sys.platform == "win32"
                    if is_windows:
                        # Su Windows il .bat attende la chiusura, copia e riavvia
                        messagebox.showinfo("Completato",
                                            "Aggiornamento scaricato!\n"
                                            "L'app si chiudera' e verra' riavviata automaticamente.",
                                            parent=app.root)
                        app.notes_ctl.save_current()
                        app.root.quit()
                    else:
                        if messagebox.askyesno("Completato", "Aggiornamento applicato!\nRiavviare ora?",
                                              parent=app.root):
                            import subprocess
                            app.notes_ctl.save_current()
                            subprocess.Popen(updater.get_restart_command())
                            app.root.quit()
                else:
                    body = "Aggiornamento fallito."
                    if last_error[0]:
                        body += f"\n\n{last_error[0]}"
                    body += "\n\nFile di log: data/mynotes.log"
                    messagebox.showerror("Errore", body, parent=app.root)
            app.root.after(0, finish)

        threading.Thread(target=do_download, daemon=True).start()
