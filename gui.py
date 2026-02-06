import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import os
import threading
import database as db
import image_utils
import platform_utils
import updater
import crypto_utils
import backup_utils
from version import VERSION
from dialogs import (CategoryDialog, NoteDialog, TagManagerDialog, AttachmentDialog,
                     VersionHistoryDialog, PasswordDialog, BackupSettingsDialog)
from annotator import AnnotationTool

UI_FONT = platform_utils.get_ui_font()
MONO_FONT = platform_utils.get_mono_font()


class MyNotesApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"MyNotes v{VERSION}")
        self.root.geometry("1200x750")
        self.root.minsize(900, 550)

        self.current_note_id = None
        self.current_category_id = None
        self.current_tag_id = None
        self.show_trash = False
        self.show_favorites = False
        self._save_job = None
        self._image_refs = []
        self._version_counter = 0  # save version every N saves
        self._decrypted_cache = {}  # note_id -> plaintext (while unlocked)

        self._setup_styles()
        self._build_menu()
        self._build_toolbar()
        self._build_main_layout()
        self._load_categories()
        self._load_notes()

        self.root.after(2000, self._check_updates_silent)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        """Handle app close: auto-backup if enabled."""
        self._save_current_note()
        settings = backup_utils.get_settings()
        if settings.get("auto_backup", True):
            try:
                backup_utils.do_local_backup()
            except Exception:
                pass
        self.root.quit()

    # --- Styling ---

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Toolbar.TFrame", background="#e0e0e0")
        style.configure("Title.TLabel", font=(UI_FONT, 13, "bold"))
        style.configure("Meta.TLabel", font=(UI_FONT, 9), foreground="#666666")
        style.configure("ImgPanel.TLabel", font=(UI_FONT, 9), foreground="#888888")
        style.configure("Pin.TLabel", font=(UI_FONT, 10), foreground="#e6a817")

    # --- Menu ---

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Nuova Nota", command=self._new_note, accelerator="Ctrl+N")
        file_menu.add_command(label="Elimina Nota", command=self._delete_note, accelerator="Del")
        file_menu.add_separator()
        file_menu.add_command(label="Esporta nota HTML...", command=self._export_html)
        file_menu.add_command(label="Esporta nota PDF...", command=self._export_pdf)
        file_menu.add_command(label="Esporta tutte (HTML)...", command=self._export_all_html)
        file_menu.add_separator()
        file_menu.add_command(label="Esci", command=self._on_close, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)

        cat_menu = tk.Menu(menubar, tearoff=0)
        cat_menu.add_command(label="Nuova Categoria", command=self._new_category)
        cat_menu.add_command(label="Rinomina Categoria", command=self._rename_category)
        cat_menu.add_command(label="Elimina Categoria", command=self._delete_category)
        menubar.add_cascade(label="Categorie", menu=cat_menu)

        note_menu = tk.Menu(menubar, tearoff=0)
        note_menu.add_command(label="Fissa/Sgancia nota", command=self._toggle_pin, accelerator="Ctrl+P")
        note_menu.add_command(label="Preferita/Non preferita", command=self._toggle_favorite, accelerator="Ctrl+D")
        note_menu.add_separator()
        note_menu.add_command(label="Gestisci Tag", command=self._manage_tags)
        note_menu.add_command(label="Allegati", command=self._manage_attachments)
        note_menu.add_command(label="Cronologia versioni", command=self._show_versions)
        note_menu.add_separator()
        note_menu.add_command(label="Cripta nota...", command=self._encrypt_note)
        note_menu.add_command(label="Decripta nota...", command=self._decrypt_note)
        note_menu.add_separator()
        note_menu.add_command(label="Inserisci checklist", command=self._insert_checklist, accelerator="Ctrl+L")
        note_menu.add_separator()
        note_menu.add_command(label="Screenshot intero", command=self._take_screenshot, accelerator="Ctrl+Shift+S")
        note_menu.add_command(label="Screenshot regione", command=self._take_screenshot_region, accelerator="Ctrl+Shift+R")
        note_menu.add_command(label="Inserisci immagine...", command=self._insert_image, accelerator="Ctrl+I")
        menubar.add_cascade(label="Nota", menu=note_menu)

        backup_menu = tk.Menu(menubar, tearoff=0)
        backup_menu.add_command(label="Backup ora", command=self._do_backup)
        backup_menu.add_command(label="Backup Google Drive", command=self._do_gdrive_backup)
        backup_menu.add_command(label="Impostazioni backup...", command=self._backup_settings)
        menubar.add_cascade(label="Backup", menu=backup_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Controlla aggiornamenti...", command=self._check_updates)
        help_menu.add_separator()
        help_menu.add_command(label=f"MyNotes v{VERSION}", state=tk.DISABLED)
        menubar.add_cascade(label="Aiuto", menu=help_menu)

        self.root.bind("<Control-n>", lambda e: self._new_note())
        self.root.bind("<Control-q>", lambda e: self._on_close())
        self.root.bind("<Control-p>", lambda e: self._toggle_pin())
        self.root.bind("<Control-d>", lambda e: self._toggle_favorite())
        self.root.bind("<Control-l>", lambda e: self._insert_checklist())
        self.root.bind("<Control-Shift-S>", lambda e: self._take_screenshot())
        self.root.bind("<Control-Shift-R>", lambda e: self._take_screenshot_region())
        self.root.bind("<Control-i>", lambda e: self._insert_image())

    # --- Toolbar ---

    def _build_toolbar(self):
        toolbar = ttk.Frame(self.root, style="Toolbar.TFrame", padding=5)
        toolbar.pack(fill=tk.X)

        ttk.Button(toolbar, text="+ Nota", command=self._new_note).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="+ Categoria", command=self._new_category).pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        ttk.Button(toolbar, text="Pin", command=self._toggle_pin).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Fav", command=self._toggle_favorite).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Tag", command=self._manage_tags).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Allegati", command=self._manage_attachments).pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        ttk.Button(toolbar, text="Screenshot", command=self._take_screenshot).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Immagine", command=self._insert_image).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Checklist", command=self._insert_checklist).pack(side=tk.LEFT, padx=2)

        ttk.Label(toolbar, text="  Cerca:").pack(side=tk.LEFT, padx=(15, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._on_search())
        ttk.Entry(toolbar, textvariable=self.search_var, width=18).pack(side=tk.LEFT)

        ttk.Label(toolbar, text="  Tag:").pack(side=tk.LEFT, padx=(10, 5))
        self.tag_filter_var = tk.StringVar()
        self.tag_combo = ttk.Combobox(toolbar, textvariable=self.tag_filter_var, state="readonly", width=12)
        self.tag_combo.pack(side=tk.LEFT)
        self.tag_combo.bind("<<ComboboxSelected>>", lambda e: self._on_tag_filter())

    # --- Main Layout ---

    def _build_main_layout(self):
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # Sidebar
        self.sidebar = tk.Frame(main_pane, bg="#2b2b2b", width=200)
        main_pane.add(self.sidebar, weight=0)

        tk.Label(self.sidebar, text="CATEGORIE", bg="#2b2b2b", fg="#888888",
                 font=(UI_FONT, 9, "bold"), anchor=tk.W, padx=12, pady=8).pack(fill=tk.X)

        self.cat_listbox = tk.Listbox(
            self.sidebar, bg="#2b2b2b", fg="#cccccc", selectbackground="#3d6fa5",
            selectforeground="#ffffff", font=(UI_FONT, 10), borderwidth=0,
            highlightthickness=0, activestyle="none"
        )
        self.cat_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.cat_listbox.bind("<<ListboxSelect>>", lambda e: self._on_category_select())

        # Center
        center = ttk.Frame(main_pane)
        main_pane.add(center, weight=1)

        self.list_header = ttk.Label(center, text="Note", style="Title.TLabel", padding=(10, 8))
        self.list_header.pack(fill=tk.X)

        self.note_listbox = tk.Listbox(
            center, font=(UI_FONT, 10), selectbackground="#4a90d9",
            selectforeground="#ffffff", borderwidth=0, highlightthickness=1,
            highlightcolor="#cccccc"
        )
        self.note_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        self.note_listbox.bind("<<ListboxSelect>>", lambda e: self._on_note_select())
        self.note_listbox.bind("<Delete>", lambda e: self._delete_note())

        # Right panel
        editor_frame = ttk.Frame(main_pane)
        main_pane.add(editor_frame, weight=3)

        title_frame = ttk.Frame(editor_frame, padding=(10, 8))
        title_frame.pack(fill=tk.X)
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(title_frame, textvariable=self.title_var, font=(UI_FONT, 14, "bold"))
        self.title_entry.pack(fill=tk.X)
        self.title_var.trace_add("write", lambda *_: self._schedule_save())

        self.meta_label = ttk.Label(editor_frame, text="", style="Meta.TLabel", padding=(12, 0))
        self.meta_label.pack(fill=tk.X)
        self.tags_label = ttk.Label(editor_frame, text="", style="Meta.TLabel", padding=(12, 2))
        self.tags_label.pack(fill=tk.X)

        editor_pane = ttk.PanedWindow(editor_frame, orient=tk.VERTICAL)
        editor_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        text_frame = ttk.Frame(editor_pane)
        editor_pane.add(text_frame, weight=3)
        self.text_editor = tk.Text(
            text_frame, font=(MONO_FONT, 11), wrap=tk.WORD,
            undo=True, borderwidth=1, relief=tk.SOLID, padx=8, pady=8
        )
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_editor.yview)
        self.text_editor.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_editor.pack(fill=tk.BOTH, expand=True)
        self.text_editor.bind("<KeyRelease>", lambda e: self._schedule_save())
        self.text_editor.bind("<Button-1>", self._on_text_click)

        # Checklist tags
        self.text_editor.tag_configure("checkbox_done", overstrike=True, foreground="#888888")
        self.text_editor.tag_configure("checkbox_open", foreground="#333333")

        # Gallery
        gallery_frame = ttk.Frame(editor_pane)
        editor_pane.add(gallery_frame, weight=1)
        gallery_header = ttk.Frame(gallery_frame)
        gallery_header.pack(fill=tk.X)
        ttk.Label(gallery_header, text="Immagini allegate", style="ImgPanel.TLabel").pack(side=tk.LEFT, padx=5)
        ttk.Button(gallery_header, text="Annota", command=self._annotate_selected_image).pack(side=tk.RIGHT, padx=2)
        ttk.Button(gallery_header, text="Apri", command=self._open_selected_image).pack(side=tk.RIGHT, padx=2)
        ttk.Button(gallery_header, text="Rimuovi", command=self._remove_selected_image).pack(side=tk.RIGHT, padx=2)

        self.gallery_canvas = tk.Canvas(gallery_frame, height=120, bg="#f5f5f5",
                                        highlightthickness=1, highlightbackground="#cccccc")
        gallery_scroll = ttk.Scrollbar(gallery_frame, orient=tk.HORIZONTAL, command=self.gallery_canvas.xview)
        self.gallery_canvas.configure(xscrollcommand=gallery_scroll.set)
        gallery_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.gallery_canvas.pack(fill=tk.BOTH, expand=True)
        self.gallery_inner = ttk.Frame(self.gallery_canvas)
        self.gallery_canvas.create_window((0, 0), window=self.gallery_inner, anchor=tk.NW)
        self.gallery_inner.bind("<Configure>",
                                lambda e: self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all")))
        self.selected_image_index = None
        self.gallery_labels = []

        # Status bar
        self.status_var = tk.StringVar(value="Pronto")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN,
                  anchor=tk.W, padding=(8, 3)).pack(fill=tk.X, side=tk.BOTTOM)

    # --- Data Loading ---

    def _load_categories(self):
        self.cat_listbox.delete(0, tk.END)
        self.cat_listbox.insert(tk.END, "  Tutte le note")
        self.cat_listbox.insert(tk.END, "  Preferite")

        self.categories = db.get_all_categories()
        for cat in self.categories:
            self.cat_listbox.insert(tk.END, f"  {cat['name']}")

        trash_count = db.get_trash_count()
        self.cat_listbox.insert(tk.END, f"  Cestino ({trash_count})")

        # Color trash entry
        last_idx = self.cat_listbox.size() - 1
        self.cat_listbox.itemconfig(last_idx, fg="#aa4444")
        self.cat_listbox.itemconfig(1, fg="#e6a817")  # Preferite in gold
        self.cat_listbox.selection_set(0)

        all_tags = db.get_all_tags()
        tag_names = ["(Tutti)"] + [t["name"] for t in all_tags]
        self.tag_combo["values"] = tag_names
        self.tag_combo.current(0)
        self.all_tags = all_tags

    def _load_notes(self):
        self.note_listbox.delete(0, tk.END)
        search = self.search_var.get().strip() or None

        self.notes = db.get_all_notes(
            category_id=self.current_category_id,
            tag_id=self.current_tag_id,
            search_query=search,
            show_deleted=self.show_trash,
            favorites_only=self.show_favorites,
        )

        for note in self.notes:
            date_str = note["updated_at"][:10]
            prefix = ""
            if note["is_pinned"]:
                prefix += "[P] "
            if note["is_favorite"]:
                prefix += "[*] "
            if note["is_encrypted"]:
                prefix += "[E] "
            self.note_listbox.insert(tk.END, f"{prefix}{note['title']}  [{date_str}]")

        header = "Cestino" if self.show_trash else ("Preferite" if self.show_favorites else "Note")
        self.list_header.config(text=f"{header} ({len(self.notes)})")
        self.status_var.set(f"{len(self.notes)} nota/e")

        if self.notes:
            self.note_listbox.selection_set(0)
            self._on_note_select()
        else:
            self._clear_editor()

    # --- Gallery ---

    def _load_gallery(self, note_id):
        self._image_refs.clear()
        for w in self.gallery_inner.winfo_children():
            w.destroy()
        self.gallery_labels.clear()
        self.selected_image_index = None

        attachments = db.get_note_attachments(note_id)
        self.gallery_attachments = [a for a in attachments if image_utils.is_image_file(a["original_name"])]

        if not self.gallery_attachments:
            ttk.Label(self.gallery_inner, text="Nessuna immagine", style="ImgPanel.TLabel").pack(side=tk.LEFT, padx=20, pady=20)
            return

        for i, att in enumerate(self.gallery_attachments):
            path = os.path.join(db.ATTACHMENTS_DIR, att["filename"])
            if not os.path.exists(path):
                continue
            try:
                photo = image_utils.load_image_as_photo(path, max_width=100, max_height=100)
                self._image_refs.append(photo)
                frame = tk.Frame(self.gallery_inner, bg="#f5f5f5", padx=4, pady=4)
                frame.pack(side=tk.LEFT, padx=3, pady=3)
                lbl = tk.Label(frame, image=photo, bg="#f5f5f5", cursor="hand2", borderwidth=2, relief=tk.FLAT)
                lbl.pack()
                tk.Label(frame, text=att["original_name"][:15], bg="#f5f5f5", font=(UI_FONT, 7), fg="#666").pack()
                lbl.bind("<Button-1>", lambda e, idx=i, l=lbl: self._select_gallery_image(idx, l))
                lbl.bind("<Double-Button-1>", lambda e, idx=i: self._open_gallery_image(idx))
                self.gallery_labels.append(lbl)
            except Exception:
                continue

    def _select_gallery_image(self, index, label):
        for lbl in self.gallery_labels:
            lbl.config(relief=tk.FLAT)
        label.config(relief=tk.SOLID)
        self.selected_image_index = index

    def _open_gallery_image(self, index):
        att = self.gallery_attachments[index]
        platform_utils.open_file(os.path.join(db.ATTACHMENTS_DIR, att["filename"]))

    def _open_selected_image(self):
        if self.selected_image_index is not None:
            self._open_gallery_image(self.selected_image_index)

    def _remove_selected_image(self):
        if self.selected_image_index is None:
            return
        att = self.gallery_attachments[self.selected_image_index]
        if messagebox.askyesno("Conferma", f"Rimuovere '{att['original_name']}'?"):
            db.delete_attachment(att["id"])
            if self.current_note_id:
                self._load_gallery(self.current_note_id)
                self._display_note(self.current_note_id)

    def _annotate_selected_image(self):
        if self.selected_image_index is None:
            messagebox.showinfo("Info", "Seleziona un'immagine dalla galleria.")
            return
        att = self.gallery_attachments[self.selected_image_index]
        path = os.path.join(db.ATTACHMENTS_DIR, att["filename"])
        if not os.path.exists(path):
            return
        tool = AnnotationTool(self.root, path)
        if tool.result_path and os.path.exists(tool.result_path):
            db.add_attachment(self.current_note_id, tool.result_path)
            os.remove(tool.result_path)
            self._load_gallery(self.current_note_id)
            self._display_note(self.current_note_id)

    # --- Event Handlers ---

    def _on_category_select(self):
        sel = self.cat_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.show_trash = False
        self.show_favorites = False
        self.current_category_id = None

        if idx == 0:  # Tutte
            pass
        elif idx == 1:  # Preferite
            self.show_favorites = True
        elif idx == self.cat_listbox.size() - 1:  # Cestino
            self.show_trash = True
        else:
            self.current_category_id = self.categories[idx - 2]["id"]
        self._load_notes()

    def _on_note_select(self):
        sel = self.note_listbox.curselection()
        if not sel:
            return
        note = self.notes[sel[0]]
        self._display_note(note["id"])

    def _on_search(self):
        if self._save_job:
            self.root.after_cancel(self._save_job)
            self._save_job = None
        self._save_current_note()
        self._load_notes()

    def _on_tag_filter(self):
        idx = self.tag_combo.current()
        self.current_tag_id = None if idx <= 0 else self.all_tags[idx - 1]["id"]
        self._load_notes()

    # --- Editor ---

    def _display_note(self, note_id):
        self._save_current_note()
        self.current_note_id = note_id
        note = db.get_note(note_id)
        if not note:
            return

        self.title_var.trace_remove("write", self.title_var.trace_info()[0][1])
        self.title_var.set(note["title"])
        self.title_var.trace_add("write", lambda *_: self._schedule_save())

        self.text_editor.delete("1.0", tk.END)

        if note["is_encrypted"]:
            if note_id in self._decrypted_cache:
                self.text_editor.insert("1.0", self._decrypted_cache[note_id])
            else:
                self.text_editor.insert("1.0", "[Nota criptata - usa Nota > Decripta nota...]")
                self.text_editor.config(state=tk.DISABLED)
        else:
            self.text_editor.config(state=tk.NORMAL)
            self.text_editor.insert("1.0", note["content"] or "")
            self._apply_checklist_formatting()

        created = note["created_at"][:16].replace("T", " ")
        updated = note["updated_at"][:16].replace("T", " ")
        meta = f"Creata: {created}  |  Modificata: {updated}"
        if note["is_pinned"]:
            meta += "  |  Fissata"
        if note["is_favorite"]:
            meta += "  |  Preferita"
        if note["is_encrypted"]:
            meta += "  |  Criptata"
        self.meta_label.config(text=meta)

        tags = db.get_note_tags(note_id)
        tag_str = "Tag: " + ", ".join(f"#{t['name']}" for t in tags) if tags else "Nessun tag"
        att_count = len(db.get_note_attachments(note_id))
        if att_count > 0:
            tag_str += f"  |  {att_count} allegato/i"
        self.tags_label.config(text=tag_str)

        self._load_gallery(note_id)

    def _clear_editor(self):
        self.current_note_id = None
        self.title_var.trace_remove("write", self.title_var.trace_info()[0][1])
        self.title_var.set("")
        self.title_var.trace_add("write", lambda *_: self._schedule_save())
        self.text_editor.config(state=tk.NORMAL)
        self.text_editor.delete("1.0", tk.END)
        self.meta_label.config(text="")
        self.tags_label.config(text="")
        self._image_refs.clear()
        for w in self.gallery_inner.winfo_children():
            w.destroy()

    def _schedule_save(self):
        if self._save_job:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(800, self._save_current_note)

    def _save_current_note(self):
        self._save_job = None
        if self.current_note_id is None:
            return
        note = db.get_note(self.current_note_id)
        if not note or note["is_encrypted"] and self.current_note_id not in self._decrypted_cache:
            return

        title = self.title_var.get().strip()
        content = self.text_editor.get("1.0", tk.END).rstrip("\n")
        if not title:
            return

        # Save version every 5 saves
        self._version_counter += 1
        if self._version_counter >= 5:
            self._version_counter = 0
            db.save_version(self.current_note_id, title, content)

        if note["is_encrypted"] and self.current_note_id in self._decrypted_cache:
            self._decrypted_cache[self.current_note_id] = content
        else:
            db.update_note(self.current_note_id, title=title, content=content)

        sel = self.note_listbox.curselection()
        if sel:
            idx = sel[0]
            date_str = datetime.now().isoformat()[:10]
            prefix = ""
            if note["is_pinned"]:
                prefix += "[P] "
            if note["is_favorite"]:
                prefix += "[*] "
            if note["is_encrypted"]:
                prefix += "[E] "
            self.note_listbox.delete(idx)
            self.note_listbox.insert(idx, f"{prefix}{title}  [{date_str}]")
            self.note_listbox.selection_set(idx)

        self.status_var.set("Salvato")

    # --- Checklist ---

    def _insert_checklist(self):
        if self.current_note_id is None:
            messagebox.showinfo("Info", "Seleziona una nota prima.")
            return
        self.text_editor.insert(tk.INSERT, "\n[ ] Elemento da fare\n[ ] Altro elemento\n[x] Elemento completato\n")
        self._apply_checklist_formatting()

    def _apply_checklist_formatting(self):
        """Apply visual formatting to checklist items."""
        self.text_editor.tag_remove("checkbox_done", "1.0", tk.END)
        self.text_editor.tag_remove("checkbox_open", "1.0", tk.END)

        content = self.text_editor.get("1.0", tk.END)
        for i, line in enumerate(content.split("\n"), 1):
            if line.strip().startswith("[x]"):
                self.text_editor.tag_add("checkbox_done", f"{i}.0", f"{i}.end")
            elif line.strip().startswith("[ ]"):
                self.text_editor.tag_add("checkbox_open", f"{i}.0", f"{i}.end")

    def _on_text_click(self, event):
        """Toggle checkbox on click."""
        index = self.text_editor.index(f"@{event.x},{event.y}")
        line_num = int(index.split(".")[0])
        line = self.text_editor.get(f"{line_num}.0", f"{line_num}.end")
        stripped = line.lstrip()

        if stripped.startswith("[ ]"):
            offset = len(line) - len(stripped)
            self.text_editor.delete(f"{line_num}.{offset}", f"{line_num}.{offset + 3}")
            self.text_editor.insert(f"{line_num}.{offset}", "[x]")
            self._apply_checklist_formatting()
            self._schedule_save()
        elif stripped.startswith("[x]"):
            offset = len(line) - len(stripped)
            self.text_editor.delete(f"{line_num}.{offset}", f"{line_num}.{offset + 3}")
            self.text_editor.insert(f"{line_num}.{offset}", "[ ]")
            self._apply_checklist_formatting()
            self._schedule_save()

    # --- Actions ---

    def _new_note(self):
        categories = db.get_all_categories()
        dlg = NoteDialog(self.root, categories)
        if dlg.result:
            note_id = db.add_note(dlg.result["title"], category_id=dlg.result["category_id"])
            self.show_trash = False
            self._load_categories()
            self._load_notes()
            for i, n in enumerate(self.notes):
                if n["id"] == note_id:
                    self.note_listbox.selection_clear(0, tk.END)
                    self.note_listbox.selection_set(i)
                    self._display_note(note_id)
                    break
            self.text_editor.focus_set()

    def _delete_note(self):
        if self.current_note_id is None:
            return
        note = db.get_note(self.current_note_id)
        if self.show_trash:
            # In trash: permanent delete or restore
            action = messagebox.askyesnocancel(
                "Cestino",
                f"'{note['title']}'\n\nSi = Elimina definitivamente\nNo = Ripristina\nAnnulla = Niente"
            )
            if action is True:
                db.permanent_delete_note(self.current_note_id)
            elif action is False:
                db.restore_note(self.current_note_id)
            else:
                return
        else:
            if messagebox.askyesno("Conferma", f"Spostare '{note['title']}' nel cestino?"):
                db.soft_delete_note(self.current_note_id)
            else:
                return
        self.current_note_id = None
        self._load_categories()
        self._load_notes()

    def _toggle_pin(self):
        if self.current_note_id is None:
            return
        db.toggle_pin(self.current_note_id)
        self._load_notes()

    def _toggle_favorite(self):
        if self.current_note_id is None:
            return
        db.toggle_favorite(self.current_note_id)
        self._load_notes()

    def _new_category(self):
        dlg = CategoryDialog(self.root, title="Nuova Categoria")
        if dlg.result:
            db.add_category(dlg.result)
            self._load_categories()

    def _rename_category(self):
        if self.current_category_id is None:
            messagebox.showinfo("Info", "Seleziona una categoria dalla sidebar.")
            return
        cat = next((c for c in self.categories if c["id"] == self.current_category_id), None)
        if not cat:
            return
        dlg = CategoryDialog(self.root, title="Rinomina Categoria", initial_name=cat["name"])
        if dlg.result:
            db.rename_category(self.current_category_id, dlg.result)
            self._load_categories()

    def _delete_category(self):
        if self.current_category_id is None:
            messagebox.showinfo("Info", "Seleziona una categoria dalla sidebar.")
            return
        cat = next((c for c in self.categories if c["id"] == self.current_category_id), None)
        if not cat:
            return
        if messagebox.askyesno("Conferma", f"Eliminare '{cat['name']}'?\nLe note non verranno eliminate."):
            db.delete_category(self.current_category_id)
            self.current_category_id = None
            self._load_categories()
            self._load_notes()

    def _manage_tags(self):
        if self.current_note_id is None:
            return
        TagManagerDialog(self.root, self.current_note_id)
        self._display_note(self.current_note_id)
        self._load_categories()

    def _manage_attachments(self):
        if self.current_note_id is None:
            return
        AttachmentDialog(self.root, self.current_note_id)
        self._display_note(self.current_note_id)

    # --- Version History ---

    def _show_versions(self):
        if self.current_note_id is None:
            return
        # Save current state as version first
        note = db.get_note(self.current_note_id)
        if note and not note["is_encrypted"]:
            content = self.text_editor.get("1.0", tk.END).rstrip("\n")
            db.save_version(self.current_note_id, note["title"], content)
        dlg = VersionHistoryDialog(self.root, self.current_note_id)
        if dlg.result:
            self._display_note(self.current_note_id)

    # --- Encryption ---

    def _encrypt_note(self):
        if self.current_note_id is None:
            return
        note = db.get_note(self.current_note_id)
        if note["is_encrypted"]:
            messagebox.showinfo("Info", "La nota e' gia' criptata.")
            return

        dlg = PasswordDialog(self.root, title="Cripta nota", confirm=True)
        if dlg.result:
            content = self.text_editor.get("1.0", tk.END).rstrip("\n")
            # Save version before encrypting
            db.save_version(self.current_note_id, note["title"], content)
            encrypted = crypto_utils.encrypt(content, dlg.result)
            db.set_note_encrypted(self.current_note_id, encrypted, True)
            self._decrypted_cache.pop(self.current_note_id, None)
            self._display_note(self.current_note_id)
            self.status_var.set("Nota criptata")

    def _decrypt_note(self):
        if self.current_note_id is None:
            return
        note = db.get_note(self.current_note_id)
        if not note["is_encrypted"]:
            messagebox.showinfo("Info", "La nota non e' criptata.")
            return

        dlg = PasswordDialog(self.root, title="Decripta nota")
        if dlg.result:
            decrypted = crypto_utils.decrypt(note["content"], dlg.result)
            if decrypted is None:
                messagebox.showerror("Errore", "Password errata.")
                return

            action = messagebox.askyesnocancel(
                "Decripta",
                "Nota decriptata!\n\nSi = Rimuovi crittografia permanentemente\n"
                "No = Visualizza solo (resta criptata)\nAnnulla = Chiudi"
            )
            if action is True:
                db.set_note_encrypted(self.current_note_id, decrypted, False)
                self._decrypted_cache.pop(self.current_note_id, None)
            elif action is False:
                self._decrypted_cache[self.current_note_id] = decrypted
            else:
                return
            self._display_note(self.current_note_id)

    # --- Export ---

    def _export_html(self):
        if self.current_note_id is None:
            return
        note = db.get_note(self.current_note_id)
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Esporta HTML",
            defaultextension=".html", initialfile=f"{note['title']}.html",
            filetypes=[("HTML", "*.html")]
        )
        if path:
            self._write_html(path, [note])
            self.status_var.set(f"Esportato: {path}")
            platform_utils.open_file(path)

    def _export_all_html(self):
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Esporta tutte le note HTML",
            defaultextension=".html", initialfile="MyNotes_export.html",
            filetypes=[("HTML", "*.html")]
        )
        if path:
            notes = db.get_all_notes()
            self._write_html(path, notes)
            self.status_var.set(f"Esportate {len(notes)} note: {path}")

    def _write_html(self, path, notes):
        import html as html_mod
        lines = ["<!DOCTYPE html><html><head><meta charset='utf-8'>",
                 "<title>MyNotes Export</title>",
                 "<style>body{font-family:sans-serif;max-width:800px;margin:auto;padding:20px}",
                 ".note{border:1px solid #ddd;padding:20px;margin:20px 0;border-radius:8px}",
                 ".note h2{margin-top:0;color:#333}.meta{color:#888;font-size:0.85em}",
                 ".checklist-done{text-decoration:line-through;color:#888}</style></head><body>",
                 "<h1>MyNotes Export</h1>"]

        for note in notes:
            content = html_mod.escape(note["content"] or "")
            # Convert checklist to HTML
            html_lines = []
            for line in content.split("\n"):
                if line.strip().startswith("[x]"):
                    html_lines.append(f'<div class="checklist-done">&#9745; {line.strip()[3:].strip()}</div>')
                elif line.strip().startswith("[ ]"):
                    html_lines.append(f'<div>&#9744; {line.strip()[3:].strip()}</div>')
                else:
                    html_lines.append(f"<p>{line}</p>" if line.strip() else "<br>")

            tags = db.get_note_tags(note["id"])
            tag_str = " ".join(f"#{t['name']}" for t in tags)

            lines.append(f'<div class="note">')
            lines.append(f'<h2>{html_mod.escape(note["title"])}</h2>')
            lines.append(f'<div class="meta">{note["created_at"][:10]} | {tag_str}</div>')
            lines.append("\n".join(html_lines))
            lines.append("</div>")

        lines.append("</body></html>")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _export_pdf(self):
        if self.current_note_id is None:
            return
        note = db.get_note(self.current_note_id)
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Esporta PDF",
            defaultextension=".pdf", initialfile=f"{note['title']}.pdf",
            filetypes=[("PDF", "*.pdf")]
        )
        if not path:
            return
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            c = canvas.Canvas(path, pagesize=A4)
            w, h = A4
            y = h - 50
            c.setFont("Helvetica-Bold", 16)
            c.drawString(40, y, note["title"])
            y -= 20
            c.setFont("Helvetica", 9)
            c.drawString(40, y, f"Creata: {note['created_at'][:10]}  |  Modificata: {note['updated_at'][:10]}")
            y -= 30
            c.setFont("Helvetica", 11)
            for line in (note["content"] or "").split("\n"):
                if y < 50:
                    c.showPage()
                    y = h - 50
                    c.setFont("Helvetica", 11)
                c.drawString(40, y, line[:100])
                y -= 15
            c.save()
            self.status_var.set(f"PDF esportato: {path}")
        except ImportError:
            messagebox.showwarning(
                "PDF",
                "Per esportare in PDF serve reportlab.\n"
                "Installa con: pip install reportlab\n\n"
                "In alternativa usa l'esportazione HTML.",
                parent=self.root
            )

    # --- Backup ---

    def _do_backup(self):
        try:
            path = backup_utils.do_local_backup()
            self.status_var.set(f"Backup creato: {os.path.basename(path)}")
            messagebox.showinfo("Backup", f"Backup salvato:\n{path}")
        except Exception as e:
            messagebox.showerror("Errore", f"Backup fallito: {e}")

    def _do_gdrive_backup(self):
        self.status_var.set("Upload Google Drive in corso...")

        def callback(success, msg):
            self.root.after(0, lambda: self._gdrive_result(success, msg))

        backup_utils.do_gdrive_backup(callback)

    def _gdrive_result(self, success, msg):
        if success:
            self.status_var.set("Backup Google Drive completato")
            messagebox.showinfo("Google Drive", msg)
        else:
            self.status_var.set("Backup Google Drive fallito")
            messagebox.showwarning("Google Drive", msg)

    def _backup_settings(self):
        BackupSettingsDialog(self.root)

    # --- Screenshot & Image ---

    def _take_screenshot(self):
        if self.current_note_id is None:
            messagebox.showinfo("Info", "Crea o seleziona una nota prima.")
            return
        self.root.withdraw()
        self.root.after(500, lambda: self._do_screenshot(full=True))

    def _take_screenshot_region(self):
        if self.current_note_id is None:
            messagebox.showinfo("Info", "Crea o seleziona una nota prima.")
            return
        self.root.withdraw()
        self.root.after(500, lambda: self._do_screenshot(full=False))

    def _do_screenshot(self, full=True):
        import uuid
        filename = f"screenshot_{uuid.uuid4().hex[:8]}.png"
        save_path = os.path.join(db.ATTACHMENTS_DIR, filename)
        try:
            success = platform_utils.take_screenshot(save_path) if full else platform_utils.take_screenshot_region(save_path)
        except Exception:
            success = False
        self.root.deiconify()
        if success and os.path.exists(save_path):
            now = datetime.now().isoformat()
            conn = db.get_connection()
            conn.execute(
                "INSERT INTO attachments (note_id, filename, original_name, added_at) VALUES (?, ?, ?, ?)",
                (self.current_note_id, filename, filename, now))
            conn.commit()
            conn.close()
            self._display_note(self.current_note_id)
            self.status_var.set("Screenshot catturato!")
        else:
            msg = "Impossibile catturare lo screenshot.\n"
            if platform_utils.IS_LINUX:
                msg += "Installa: sudo dnf install grim slurp"
            messagebox.showwarning("Screenshot", msg, parent=self.root)

    def _insert_image(self):
        if self.current_note_id is None:
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="Seleziona immagine",
            filetypes=[("Immagini", "*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.webp"), ("Tutti", "*.*")])
        if path:
            db.add_attachment(self.current_note_id, path)
            self._display_note(self.current_note_id)
            self.status_var.set(f"Immagine aggiunta")

    # --- Auto-Update ---

    def _check_updates_silent(self):
        def check():
            result = updater.check_for_updates()
            if result:
                self.root.after(0, lambda: self.status_var.set(
                    f"Aggiornamento disponibile: {result[0]} (Aiuto > Controlla aggiornamenti)"))
        threading.Thread(target=check, daemon=True).start()

    def _check_updates(self):
        self.status_var.set("Controllo aggiornamenti...")
        def check():
            result = updater.check_for_updates()
            self.root.after(0, lambda: self._handle_update_result(result))
        threading.Thread(target=check, daemon=True).start()

    def _handle_update_result(self, result):
        if result is None:
            self.status_var.set("Nessun aggiornamento")
            messagebox.showinfo("Aggiornamenti", f"MyNotes v{VERSION} e' aggiornato!")
            return
        tag, url, notes = result
        msg = f"Nuova versione: {tag}\n(Attuale: v{VERSION})\n\nAggiornare?"
        if messagebox.askyesno("Aggiornamento", msg):
            self._do_update(url)

    def _do_update(self, download_url):
        progress_win = tk.Toplevel(self.root)
        progress_win.title("Aggiornamento")
        progress_win.geometry("400x100")
        progress_win.resizable(False, False)
        progress_win.grab_set()
        progress_win.transient(self.root)
        frame = ttk.Frame(progress_win, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        status_label = ttk.Label(frame, text="Preparazione...")
        status_label.pack(anchor=tk.W)
        progress_bar = ttk.Progressbar(frame, mode="determinate", maximum=100)
        progress_bar.pack(fill=tk.X, pady=(10, 0))

        def on_progress(pct, msg):
            self.root.after(0, lambda: (status_label.config(text=msg),
                                         progress_bar.__setitem__("value", max(0, pct))))

        def do_download():
            success = updater.download_and_apply_update(download_url, on_progress)
            def finish():
                progress_win.destroy()
                if success:
                    if messagebox.askyesno("Completato", "Aggiornamento applicato!\nRiavviare ora?"):
                        import subprocess
                        subprocess.Popen(updater.get_restart_command())
                        self.root.quit()
                else:
                    messagebox.showerror("Errore", "Aggiornamento fallito.")
            self.root.after(0, finish)

        threading.Thread(target=do_download, daemon=True).start()
