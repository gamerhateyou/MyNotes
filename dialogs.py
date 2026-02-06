import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import database as db
import platform_utils


class CategoryDialog(tk.Toplevel):
    """Dialog to add or rename a category."""

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
    """Dialog to create a new note."""

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
    """Dialog to manage tags for a note."""

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
    """Dialog to view and manage attachments for a note."""

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
