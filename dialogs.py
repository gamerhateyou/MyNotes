import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import database as db
import platform_utils
import audio_utils


class CategoryDialog(tk.Toplevel):
    def __init__(self, parent, title="Nuova Categoria", initial_name=""):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.resizable(False, False)
        self.grab_set()

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Nome categoria:").pack(anchor=tk.W)
        self.entry = ttk.Entry(frame, width=35)
        self.entry.insert(0, initial_name)
        self.entry.pack(pady=(5, 15))
        self.entry.focus_set()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Annulla", command=self.destroy).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side=tk.RIGHT)
        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.transient(parent)
        self.wait_window()

    def _on_ok(self):
        name = self.entry.get().strip()
        if name:
            self.result = name
            self.destroy()


class NoteDialog(tk.Toplevel):
    def __init__(self, parent, categories):
        super().__init__(parent)
        self.title("Nuova Nota")
        self.result = None
        self.resizable(False, False)
        self.grab_set()
        self.categories = categories

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Titolo:").pack(anchor=tk.W)
        self.title_entry = ttk.Entry(frame, width=40)
        self.title_entry.pack(pady=(5, 10))
        self.title_entry.focus_set()

        ttk.Label(frame, text="Categoria:").pack(anchor=tk.W)
        self.cat_var = tk.StringVar()
        cat_names = ["(Nessuna)"] + [c["name"] for c in categories]
        self.cat_combo = ttk.Combobox(frame, textvariable=self.cat_var, values=cat_names, state="readonly", width=37)
        self.cat_combo.current(0)
        self.cat_combo.pack(pady=(5, 15))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Annulla", command=self.destroy).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="Crea", command=self._on_ok).pack(side=tk.RIGHT)
        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.transient(parent)
        self.wait_window()

    def _on_ok(self):
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showwarning("Attenzione", "Inserisci un titolo.", parent=self)
            return
        cat_id = None
        idx = self.cat_combo.current()
        if idx > 0:
            cat_id = self.categories[idx - 1]["id"]
        self.result = {"title": title, "category_id": cat_id}
        self.destroy()


class TagManagerDialog(tk.Toplevel):
    def __init__(self, parent, note_id):
        super().__init__(parent)
        self.title("Gestione Tag")
        self.note_id = note_id
        self.resizable(False, False)
        self.grab_set()

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        add_frame = ttk.Frame(frame)
        add_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(add_frame, text="Nuovo tag:").pack(side=tk.LEFT)
        self.new_tag_entry = ttk.Entry(add_frame, width=20)
        self.new_tag_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(add_frame, text="Aggiungi", command=self._add_tag).pack(side=tk.LEFT)

        ttk.Label(frame, text="Tag disponibili:").pack(anchor=tk.W)
        self.check_frame = ttk.Frame(frame)
        self.check_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.tag_vars = {}
        self._load_tags()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="Chiudi", command=self._on_close).pack(side=tk.RIGHT)
        self.bind("<Escape>", lambda e: self._on_close())
        self.transient(parent)
        self.wait_window()

    def _load_tags(self):
        for w in self.check_frame.winfo_children():
            w.destroy()
        all_tags = db.get_all_tags()
        note_tags = db.get_note_tags(self.note_id)
        note_tag_ids = {t["id"] for t in note_tags}
        self.tag_vars = {}
        for tag in all_tags:
            var = tk.BooleanVar(value=tag["id"] in note_tag_ids)
            self.tag_vars[tag["id"]] = var
            ttk.Checkbutton(self.check_frame, text=tag["name"], variable=var).pack(anchor=tk.W)
        if not all_tags:
            ttk.Label(self.check_frame, text="Nessun tag creato.").pack()

    def _add_tag(self):
        name = self.new_tag_entry.get().strip()
        if name:
            db.add_tag(name)
            self.new_tag_entry.delete(0, tk.END)
            self._load_tags()

    def _on_close(self):
        selected_ids = [tid for tid, var in self.tag_vars.items() if var.get()]
        db.set_note_tags(self.note_id, selected_ids)
        self.destroy()


class AttachmentDialog(tk.Toplevel):
    def __init__(self, parent, note_id):
        super().__init__(parent)
        self.title("Allegati")
        self.note_id = note_id
        self.geometry("450x350")
        self.grab_set()

        frame = ttk.Frame(self, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(toolbar, text="Aggiungi file...", command=self._add_file).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Rimuovi selezionato", command=self._remove_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Apri file", command=self._open_file).pack(side=tk.LEFT)

        self.listbox = tk.Listbox(frame, selectmode=tk.SINGLE)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.attachments = []
        self._load_attachments()

        ttk.Button(frame, text="Chiudi", command=self.destroy).pack(pady=(10, 0), anchor=tk.E)
        self.bind("<Escape>", lambda e: self.destroy())
        self.transient(parent)
        self.wait_window()

    def _load_attachments(self):
        self.listbox.delete(0, tk.END)
        self.attachments = db.get_note_attachments(self.note_id)
        for att in self.attachments:
            self.listbox.insert(tk.END, f"{att['original_name']}  ({att['added_at'][:10]})")

    def _add_file(self):
        path = filedialog.askopenfilename(parent=self, title="Seleziona file da allegare")
        if path:
            db.add_attachment(self.note_id, path)
            self._load_attachments()

    def _remove_file(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        att = self.attachments[sel[0]]
        if messagebox.askyesno("Conferma", f"Rimuovere '{att['original_name']}'?", parent=self):
            db.delete_attachment(att["id"])
            self._load_attachments()

    def _open_file(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        att = self.attachments[sel[0]]
        import os
        path = os.path.join(db.ATTACHMENTS_DIR, att["filename"])
        if not platform_utils.open_file(path):
            messagebox.showerror("Errore", "Impossibile aprire il file.", parent=self)


class VersionHistoryDialog(tk.Toplevel):
    """Dialog to view and restore note version history."""

    def __init__(self, parent, note_id):
        super().__init__(parent)
        self.title("Cronologia versioni")
        self.note_id = note_id
        self.result = None
        self.geometry("600x450")
        self.grab_set()

        frame = ttk.Frame(self, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Versioni salvate:", font=("Sans", 10, "bold")).pack(anchor=tk.W)

        # Version list
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.version_list = tk.Listbox(list_frame, font=("Sans", 10))
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.version_list.yview)
        self.version_list.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.version_list.pack(fill=tk.BOTH, expand=True)
        self.version_list.bind("<<ListboxSelect>>", lambda e: self._on_select())

        # Preview
        ttk.Label(frame, text="Anteprima:").pack(anchor=tk.W, pady=(5, 0))
        self.preview = tk.Text(frame, height=8, font=("Monospace", 10), state=tk.DISABLED,
                               wrap=tk.WORD, bg="#f8f8f8")
        self.preview.pack(fill=tk.BOTH, expand=True, pady=5)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Chiudi", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Ripristina questa versione", command=self._restore).pack(side=tk.RIGHT, padx=5)

        self.versions = db.get_note_versions(note_id)
        for v in self.versions:
            date = v["saved_at"][:19].replace("T", " ")
            title = v["title"][:40]
            self.version_list.insert(tk.END, f"[{date}]  {title}")

        if not self.versions:
            self.version_list.insert(tk.END, "Nessuna versione precedente salvata.")

        self.bind("<Escape>", lambda e: self.destroy())
        self.transient(parent)
        self.wait_window()

    def _on_select(self):
        sel = self.version_list.curselection()
        if not sel or not self.versions:
            return
        ver = self.versions[sel[0]]
        self.preview.config(state=tk.NORMAL)
        self.preview.delete("1.0", tk.END)
        self.preview.insert("1.0", ver["content"] or "")
        self.preview.config(state=tk.DISABLED)

    def _restore(self):
        sel = self.version_list.curselection()
        if not sel or not self.versions:
            return
        ver = self.versions[sel[0]]
        if messagebox.askyesno("Ripristina", "Ripristinare questa versione?\nLa versione attuale verrà salvata.", parent=self):
            # Save current version first
            note = db.get_note(self.note_id)
            if note:
                db.save_version(self.note_id, note["title"], note["content"])
            db.restore_version(self.note_id, ver["id"])
            self.result = True
            self.destroy()


class PasswordDialog(tk.Toplevel):
    """Dialog to enter encryption password."""

    def __init__(self, parent, title="Password", confirm=False):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.resizable(False, False)
        self.grab_set()

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Password:").pack(anchor=tk.W)
        self.pw_entry = ttk.Entry(frame, show="*", width=30)
        self.pw_entry.pack(pady=(5, 10))
        self.pw_entry.focus_set()

        if confirm:
            ttk.Label(frame, text="Conferma password:").pack(anchor=tk.W)
            self.pw_confirm = ttk.Entry(frame, show="*", width=30)
            self.pw_confirm.pack(pady=(5, 10))
        else:
            self.pw_confirm = None

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Annulla", command=self.destroy).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side=tk.RIGHT)

        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.transient(parent)
        self.wait_window()

    def _on_ok(self):
        pw = self.pw_entry.get()
        if not pw:
            messagebox.showwarning("Attenzione", "Inserisci una password.", parent=self)
            return
        if self.pw_confirm is not None:
            if pw != self.pw_confirm.get():
                messagebox.showwarning("Attenzione", "Le password non coincidono.", parent=self)
                return
        self.result = pw
        self.destroy()


class AudioRecordDialog(tk.Toplevel):
    """Dialog per registrazione audio o descrizione per import audio."""

    def __init__(self, parent, mode="record", audio_path=None):
        super().__init__(parent)
        self.mode = mode
        self.audio_path = audio_path
        self.result = None
        self._timer_id = None
        self._elapsed = 0
        self._recording = False
        self._temp_path = None
        self.resizable(False, False)
        self.grab_set()

        if mode == "record":
            self.title("Registra Audio")
            self._build_record_ui()
        else:
            self.title("Descrizione Audio")
            self._build_describe_ui()

        self.bind("<Escape>", lambda e: self._on_cancel())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.transient(parent)
        self.wait_window()

    def _build_record_ui(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Descrizione (opzionale):").pack(anchor=tk.W)
        self.desc_entry = ttk.Entry(frame, width=40)
        self.desc_entry.pack(pady=(5, 10))
        self.desc_entry.focus_set()

        # Timer
        self.timer_label = ttk.Label(frame, text="00:00", font=("Sans", 18, "bold"))
        self.timer_label.pack(pady=10)

        # Status
        self.status_label = ttk.Label(frame, text="Pronto per registrare", foreground="#888888")
        self.status_label.pack(pady=(0, 10))

        # Record/Stop buttons
        rec_frame = ttk.Frame(frame)
        rec_frame.pack(fill=tk.X, pady=5)
        self.rec_btn = ttk.Button(rec_frame, text="Registra", command=self._toggle_record)
        self.rec_btn.pack(side=tk.LEFT, padx=2)
        self.preview_btn = ttk.Button(rec_frame, text="Anteprima", command=self._preview, state=tk.DISABLED)
        self.preview_btn.pack(side=tk.LEFT, padx=2)

        # Check sounddevice availability
        if not audio_utils.is_available():
            self.rec_btn.config(state=tk.DISABLED)
            self.status_label.config(
                text="Libreria 'sounddevice' non installata.\npip install sounddevice",
                foreground="#cc0000"
            )

        ttk.Separator(frame).pack(fill=tk.X, pady=10)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Annulla", command=self._on_cancel).pack(side=tk.RIGHT, padx=(5, 0))
        self.save_btn = ttk.Button(btn_frame, text="Salva", command=self._on_save, state=tk.DISABLED)
        self.save_btn.pack(side=tk.RIGHT)

    def _build_describe_ui(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        filename = os.path.basename(self.audio_path) if self.audio_path else ""
        ttk.Label(frame, text=f"File: {filename}").pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(frame, text="Descrizione (opzionale):").pack(anchor=tk.W)
        self.desc_entry = ttk.Entry(frame, width=40)
        self.desc_entry.pack(pady=(5, 15))
        self.desc_entry.focus_set()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Annulla", command=self._on_cancel).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="OK", command=self._on_save).pack(side=tk.RIGHT)
        self.bind("<Return>", lambda e: self._on_save())

    def _toggle_record(self):
        if not self._recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        self._temp_path = audio_utils.get_temp_wav_path()
        try:
            audio_utils.record_audio()
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile avviare la registrazione:\n{e}", parent=self)
            return
        self._recording = True
        self._elapsed = 0
        self.rec_btn.config(text="Stop")
        self.preview_btn.config(state=tk.DISABLED)
        self.save_btn.config(state=tk.DISABLED)
        self.status_label.config(text="Registrazione in corso...", foreground="#cc0000")
        self._update_timer()

    def _stop_recording(self):
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None
        self._recording = False
        audio_utils.stop_recording(self._temp_path)
        self.rec_btn.config(text="Registra")
        self.preview_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Registrazione completata", foreground="#228B22")

    def _update_timer(self):
        if not self._recording:
            return
        self._elapsed += 1
        mins, secs = divmod(self._elapsed, 60)
        self.timer_label.config(text=f"{mins:02d}:{secs:02d}")
        self._timer_id = self.after(1000, self._update_timer)

    def _preview(self):
        if self._temp_path and os.path.exists(self._temp_path):
            platform_utils.open_file(self._temp_path)

    def _on_save(self):
        if self._recording:
            self._stop_recording()

        desc = self.desc_entry.get().strip()

        if self.mode == "record":
            if not self._temp_path or not os.path.exists(self._temp_path):
                messagebox.showwarning("Attenzione", "Nessuna registrazione effettuata.", parent=self)
                return
            self.result = {"path": self._temp_path, "description": desc}
        else:
            self.result = {"path": self.audio_path, "description": desc}
        self.destroy()

    def _on_cancel(self):
        if self._recording:
            self._stop_recording()
        # Cleanup temp file on cancel
        if self.mode == "record" and self._temp_path and os.path.exists(self._temp_path):
            try:
                os.remove(self._temp_path)
            except OSError:
                pass
        self.result = None
        self.destroy()


class BackupSettingsDialog(tk.Toplevel):
    """Dialog to configure backup settings with integrated Google Drive auth."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Impostazioni Backup")
        self.resizable(False, False)
        self.grab_set()

        import backup_utils
        self.backup_utils = backup_utils
        self.settings = backup_utils.get_settings()

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # --- Local Backup ---
        ttk.Label(frame, text="Backup Locale", font=("Sans", 10, "bold")).pack(anchor=tk.W)

        self.auto_var = tk.BooleanVar(value=self.settings.get("auto_backup", True))
        ttk.Checkbutton(frame, text="Backup automatico alla chiusura", variable=self.auto_var).pack(anchor=tk.W, pady=(5, 0))

        dir_frame = ttk.Frame(frame)
        dir_frame.pack(fill=tk.X, pady=(10, 5))
        ttk.Label(dir_frame, text="Cartella backup locale:").pack(anchor=tk.W)
        self.dir_var = tk.StringVar(value=self.settings.get("local_backup_dir", ""))
        ttk.Entry(dir_frame, textvariable=self.dir_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(dir_frame, text="...", width=3,
                   command=self._browse_dir).pack(side=tk.LEFT, padx=5)

        max_frame = ttk.Frame(frame)
        max_frame.pack(fill=tk.X, pady=5)
        ttk.Label(max_frame, text="Max backup locali:").pack(side=tk.LEFT)
        self.max_var = tk.IntVar(value=self.settings.get("max_local_backups", 10))
        ttk.Spinbox(max_frame, from_=1, to=100, textvariable=self.max_var, width=5).pack(side=tk.LEFT, padx=5)

        ret_frame = ttk.Frame(frame)
        ret_frame.pack(fill=tk.X, pady=5)
        ttk.Label(ret_frame, text="Cancella backup piu vecchi di (giorni):").pack(side=tk.LEFT)
        self.retention_var = tk.IntVar(value=self.settings.get("retention_days", 90))
        ttk.Spinbox(ret_frame, from_=0, to=365, textvariable=self.retention_var, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Label(ret_frame, text="0 = mai", foreground="#888888").pack(side=tk.LEFT)

        # --- Google Drive ---
        ttk.Separator(frame).pack(fill=tk.X, pady=10)
        ttk.Label(frame, text="Google Drive", font=("Sans", 10, "bold")).pack(anchor=tk.W)

        # Connection status
        status_frame = ttk.Frame(frame)
        status_frame.pack(fill=tk.X, pady=(5, 5))

        self.status_label = ttk.Label(status_frame, text="")
        self.status_label.pack(side=tk.LEFT)

        self.auth_btn = ttk.Button(status_frame, text="", command=self._toggle_gdrive_auth)
        self.auth_btn.pack(side=tk.RIGHT)

        self._update_gdrive_status()

        # Enable checkbox
        self.gdrive_var = tk.BooleanVar(value=self.settings.get("gdrive_enabled", False))
        self.gdrive_check = ttk.Checkbutton(frame, text="Abilita backup su Google Drive",
                                            variable=self.gdrive_var)
        self.gdrive_check.pack(anchor=tk.W, pady=(5, 0))

        # Folder name
        folder_frame = ttk.Frame(frame)
        folder_frame.pack(fill=tk.X, pady=5)
        ttk.Label(folder_frame, text="Nome cartella su Drive:").pack(anchor=tk.W)
        self.folder_var = tk.StringVar(value=self.settings.get("gdrive_folder_name", "MyNotes Backup"))
        ttk.Entry(folder_frame, textvariable=self.folder_var, width=40).pack(fill=tk.X)

        gdrive_max_frame = ttk.Frame(frame)
        gdrive_max_frame.pack(fill=tk.X, pady=5)
        ttk.Label(gdrive_max_frame, text="Max backup su Drive:").pack(side=tk.LEFT)
        self.gdrive_max_var = tk.IntVar(value=self.settings.get("max_gdrive_backups", 20))
        ttk.Spinbox(gdrive_max_frame, from_=0, to=100, textvariable=self.gdrive_max_var, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Label(gdrive_max_frame, text="0 = illimitato", foreground="#888888").pack(side=tk.LEFT)

        # --- Crittografia ---
        ttk.Separator(frame).pack(fill=tk.X, pady=10)
        ttk.Label(frame, text="Crittografia", font=("Sans", 10, "bold")).pack(anchor=tk.W)

        self.encrypt_var = tk.BooleanVar(value=self.settings.get("encrypt_backups", False))
        ttk.Checkbutton(frame, text="Cripta backup con password",
                        variable=self.encrypt_var).pack(anchor=tk.W, pady=(5, 0))

        pw_status = "Password impostata" if backup_utils._get_backup_password() else "Password non impostata"
        pw_color = "#228B22" if backup_utils._get_backup_password() else "#888888"
        self.pw_status_label = ttk.Label(frame, text=pw_status, foreground=pw_color)
        self.pw_status_label.pack(anchor=tk.W, pady=(2, 0))

        # --- Scheduler ---
        ttk.Separator(frame).pack(fill=tk.X, pady=10)
        ttk.Label(frame, text="Backup Automatico", font=("Sans", 10, "bold")).pack(anchor=tk.W)

        interval_frame = ttk.Frame(frame)
        interval_frame.pack(fill=tk.X, pady=(5, 5))
        ttk.Label(interval_frame, text="Intervallo backup:").pack(side=tk.LEFT)

        self._interval_labels = ["Disabilitato", "30 minuti", "1 ora", "2 ore",
                                 "4 ore", "8 ore", "12 ore", "24 ore"]
        self._interval_values = [0, 30, 60, 120, 240, 480, 720, 1440]
        self.interval_combo = ttk.Combobox(interval_frame, values=self._interval_labels,
                                           state="readonly", width=15)
        current_interval = self.settings.get("backup_interval_minutes", 0)
        idx = self._interval_values.index(current_interval) if current_interval in self._interval_values else 0
        self.interval_combo.current(idx)
        self.interval_combo.pack(side=tk.LEFT, padx=5)

        last_backup = self.settings.get("last_backup_time", "")
        last_text = f"Ultimo backup: {last_backup}" if last_backup else "Ultimo backup: mai"
        ttk.Label(frame, text=last_text, foreground="#888888").pack(anchor=tk.W, pady=(2, 0))

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        ttk.Button(btn_frame, text="Annulla", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Salva", command=self._save).pack(side=tk.RIGHT, padx=5)

        self.bind("<Escape>", lambda e: self.destroy())
        self.transient(parent)
        self.wait_window()

    def _update_gdrive_status(self):
        if self.backup_utils.is_gdrive_configured():
            self.status_label.config(text="Connesso a Google Drive", foreground="#228B22")
            self.auth_btn.config(text="Disconnetti")
        else:
            self.status_label.config(text="Non connesso", foreground="#888888")
            self.auth_btn.config(text="Accedi con Google")

    def _toggle_gdrive_auth(self):
        if self.backup_utils.is_gdrive_configured():
            if messagebox.askyesno("Disconnetti", "Rimuovere l'autorizzazione Google Drive?", parent=self):
                self.backup_utils.gdrive_disconnect()
                self.gdrive_var.set(False)
                self._update_gdrive_status()
        else:
            self.auth_btn.config(state=tk.DISABLED, text="Autorizzazione in corso...")
            self.update_idletasks()

            import threading

            def _do_auth():
                success, msg = self.backup_utils.gdrive_authorize()
                self.after(0, lambda: self._auth_done(success, msg))

            threading.Thread(target=_do_auth, daemon=True).start()

    def _auth_done(self, success, msg):
        self.auth_btn.config(state=tk.NORMAL)
        if success:
            messagebox.showinfo("Google Drive", msg, parent=self)
        else:
            messagebox.showerror("Errore", msg, parent=self)
        self._update_gdrive_status()

    def _browse_dir(self):
        d = filedialog.askdirectory(parent=self, title="Cartella backup")
        if d:
            self.dir_var.set(d)

    def _save(self):
        self.settings["auto_backup"] = self.auto_var.get()
        self.settings["local_backup_dir"] = self.dir_var.get()
        self.settings["max_local_backups"] = self.max_var.get()
        self.settings["retention_days"] = self.retention_var.get()
        self.settings["gdrive_enabled"] = self.gdrive_var.get()
        self.settings["gdrive_folder_name"] = self.folder_var.get()
        self.settings["max_gdrive_backups"] = self.gdrive_max_var.get()

        # Crittografia backup
        encrypt = self.encrypt_var.get()
        self.settings["encrypt_backups"] = encrypt
        if encrypt and not self.backup_utils._get_backup_password():
            # Chiedi password se non impostata
            pwd_dlg = PasswordDialog(self, title="Password backup", confirm=True)
            if pwd_dlg.result:
                self.backup_utils.set_backup_password(pwd_dlg.result)
            else:
                self.settings["encrypt_backups"] = False

        # Scheduler
        self.settings["backup_interval_minutes"] = self._interval_values[self.interval_combo.current()]

        self.backup_utils.save_settings(self.settings)
        messagebox.showinfo("Salvato", "Impostazioni backup salvate.", parent=self)
        self.destroy()


class BackupRestoreDialog(tk.Toplevel):
    """Dialog per selezionare e ripristinare un backup."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Ripristina Backup")
        self.result = None
        self.geometry("650x500")
        self.grab_set()

        import backup_utils
        self.backup_utils = backup_utils

        frame = ttk.Frame(self, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Backup disponibili:", font=("Sans", 10, "bold")).pack(anchor=tk.W)

        # Backup list
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.backup_list = tk.Listbox(list_frame, font=("Sans", 10))
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.backup_list.yview)
        self.backup_list.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.backup_list.pack(fill=tk.BOTH, expand=True)
        self.backup_list.bind("<<ListboxSelect>>", lambda e: self._on_select())

        # Pannello dettagli
        detail_frame = ttk.LabelFrame(frame, text="Dettagli", padding=10)
        detail_frame.pack(fill=tk.X, pady=5)

        self.detail_date = ttk.Label(detail_frame, text="Data: -")
        self.detail_date.pack(anchor=tk.W)
        self.detail_size = ttk.Label(detail_frame, text="Dimensione: -")
        self.detail_size.pack(anchor=tk.W)
        self.detail_notes = ttk.Label(detail_frame, text="Note: -")
        self.detail_notes.pack(anchor=tk.W)
        self.detail_integrity = ttk.Label(detail_frame, text="Integrita': -")
        self.detail_integrity.pack(anchor=tk.W)
        self.detail_checksum = ttk.Label(detail_frame, text="Checksum: -")
        self.detail_checksum.pack(anchor=tk.W)
        self.detail_encrypted = ttk.Label(detail_frame, text="")
        self.detail_encrypted.pack(anchor=tk.W)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_frame, text="Chiudi", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Ripristina", command=self._restore).pack(side=tk.RIGHT, padx=5)

        # Carica lista backup
        settings = backup_utils.get_settings()
        backup_dir = settings.get("local_backup_dir", db.BACKUP_DIR)
        self.backups = db.get_backups(backup_dir)
        for b in self.backups:
            enc_label = " [crittografato]" if b["encrypted"] else ""
            size_kb = b["size"] / 1024
            self.backup_list.insert(
                tk.END,
                f"{b['date_str']}  ({size_kb:.0f} KB){enc_label}"
            )

        if not self.backups:
            self.backup_list.insert(tk.END, "Nessun backup disponibile.")

        self.bind("<Escape>", lambda e: self.destroy())
        self.transient(parent)
        self.wait_window()

    def _on_select(self):
        sel = self.backup_list.curselection()
        if not sel or not self.backups:
            return
        b = self.backups[sel[0]]
        self.detail_date.config(text=f"Data: {b['date_str']}")
        size_kb = b["size"] / 1024
        self.detail_size.config(text=f"Dimensione: {size_kb:.1f} KB")

        if b["encrypted"]:
            self.detail_encrypted.config(text="Crittografato: Si'")
            self.detail_notes.config(text="Note: (richiede password)")
            self.detail_integrity.config(text="Integrita': (richiede decrittografia)")
        else:
            self.detail_encrypted.config(text="")
            count = self.backup_utils.get_note_count_from_backup(b["path"])
            self.detail_notes.config(text=f"Note: {count}" if count >= 0 else "Note: errore lettura")
            ok, msg = self.backup_utils.verify_backup_integrity(b["path"])
            color = "#228B22" if ok else "#cc0000"
            self.detail_integrity.config(text=f"Integrita': {msg}", foreground=color)

        ok_cs, msg_cs = self.backup_utils.verify_checksum(b["path"])
        if ok_cs is True:
            color_cs = "#228B22"
        elif ok_cs is False:
            color_cs = "#cc0000"
        else:
            color_cs = "#888888"
        self.detail_checksum.config(text=f"Checksum: {msg_cs}", foreground=color_cs)

    def _restore(self):
        sel = self.backup_list.curselection()
        if not sel or not self.backups:
            return
        b = self.backups[sel[0]]
        password = None

        if b["encrypted"]:
            pwd_dlg = PasswordDialog(self, title="Password backup")
            if not pwd_dlg.result:
                return
            password = pwd_dlg.result

        msg = ("Il database attuale verra' sostituito.\n"
               "Un backup di sicurezza verra' creato automaticamente.\n\n"
               "Continuare con il ripristino?")
        if not messagebox.askyesno("Conferma ripristino", msg, parent=self):
            return

        self.result = {"path": b["path"], "password": password}
        self.destroy()
