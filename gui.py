import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import os
import threading
import database as db
import image_utils
import platform_utils
import updater
from version import VERSION
from dialogs import CategoryDialog, NoteDialog, TagManagerDialog, AttachmentDialog
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
        self._save_job = None
        self._image_refs = []

        self._setup_styles()
        self._build_menu()
        self._build_toolbar()
        self._build_main_layout()
        self._load_categories()
        self._load_notes()

        # Check aggiornamenti in background all'avvio
        self.root.after(2000, self._check_updates_silent)

    # --- Styling ---

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Sidebar.TFrame", background="#2b2b2b")
        style.configure("Sidebar.TLabel", background="#2b2b2b", foreground="#ffffff", font=(UI_FONT, 11, "bold"))
        style.configure("SidebarItem.TLabel", background="#2b2b2b", foreground="#cccccc", font=(UI_FONT, 10))
        style.configure("SidebarItemSel.TLabel", background="#3d6fa5", foreground="#ffffff", font=(UI_FONT, 10, "bold"))
        style.configure("Toolbar.TFrame", background="#e0e0e0")
        style.configure("Title.TLabel", font=(UI_FONT, 13, "bold"))
        style.configure("Meta.TLabel", font=(UI_FONT, 9), foreground="#666666")
        style.configure("ImgPanel.TLabel", font=(UI_FONT, 9), foreground="#888888")

    # --- Menu ---

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Nuova Nota", command=self._new_note, accelerator="Ctrl+N")
        file_menu.add_command(label="Elimina Nota", command=self._delete_note, accelerator="Del")
        file_menu.add_separator()
        file_menu.add_command(label="Esci", command=self.root.quit, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)

        cat_menu = tk.Menu(menubar, tearoff=0)
        cat_menu.add_command(label="Nuova Categoria", command=self._new_category)
        cat_menu.add_command(label="Rinomina Categoria", command=self._rename_category)
        cat_menu.add_command(label="Elimina Categoria", command=self._delete_category)
        menubar.add_cascade(label="Categorie", menu=cat_menu)

        note_menu = tk.Menu(menubar, tearoff=0)
        note_menu.add_command(label="Gestisci Tag", command=self._manage_tags)
        note_menu.add_command(label="Allegati", command=self._manage_attachments)
        note_menu.add_separator()
        note_menu.add_command(label="Screenshot intero", command=self._take_screenshot, accelerator="Ctrl+Shift+S")
        note_menu.add_command(label="Screenshot regione", command=self._take_screenshot_region, accelerator="Ctrl+Shift+R")
        note_menu.add_command(label="Inserisci immagine...", command=self._insert_image, accelerator="Ctrl+I")
        menubar.add_cascade(label="Nota", menu=note_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Controlla aggiornamenti...", command=self._check_updates)
        help_menu.add_separator()
        help_menu.add_command(label=f"MyNotes v{VERSION}", state=tk.DISABLED)
        menubar.add_cascade(label="Aiuto", menu=help_menu)

        self.root.bind("<Control-n>", lambda e: self._new_note())
        self.root.bind("<Control-q>", lambda e: self.root.quit())
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

        ttk.Button(toolbar, text="Tag", command=self._manage_tags).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Allegati", command=self._manage_attachments).pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        ttk.Button(toolbar, text="Screenshot", command=self._take_screenshot).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Regione", command=self._take_screenshot_region).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Immagine", command=self._insert_image).pack(side=tk.LEFT, padx=2)

        ttk.Label(toolbar, text="  Cerca:").pack(side=tk.LEFT, padx=(15, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._on_search())
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT)

        ttk.Label(toolbar, text="  Tag:").pack(side=tk.LEFT, padx=(10, 5))
        self.tag_filter_var = tk.StringVar()
        self.tag_combo = ttk.Combobox(toolbar, textvariable=self.tag_filter_var, state="readonly", width=15)
        self.tag_combo.pack(side=tk.LEFT)
        self.tag_combo.bind("<<ComboboxSelected>>", lambda e: self._on_tag_filter())

    # --- Main Layout ---

    def _build_main_layout(self):
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # Sidebar
        self.sidebar = tk.Frame(main_pane, bg="#2b2b2b", width=200)
        main_pane.add(self.sidebar, weight=0)

        sidebar_title = tk.Label(self.sidebar, text="CATEGORIE", bg="#2b2b2b", fg="#888888",
                                 font=(UI_FONT, 9, "bold"), anchor=tk.W, padx=12, pady=8)
        sidebar_title.pack(fill=tk.X)

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

        list_header = ttk.Label(center, text="Note", style="Title.TLabel", padding=(10, 8))
        list_header.pack(fill=tk.X)

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

        # Text editor
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

        # Image gallery
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
        self.gallery_window = self.gallery_canvas.create_window((0, 0), window=self.gallery_inner, anchor=tk.NW)
        self.gallery_inner.bind("<Configure>",
                                lambda e: self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all")))

        self.selected_image_index = None
        self.gallery_labels = []

        # Status bar
        self.status_var = tk.StringVar(value="Pronto")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=(8, 3))
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # --- Data Loading ---

    def _load_categories(self):
        self.cat_listbox.delete(0, tk.END)
        self.cat_listbox.insert(tk.END, "  Tutte le note")
        self.categories = db.get_all_categories()
        for cat in self.categories:
            self.cat_listbox.insert(tk.END, f"  {cat['name']}")
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
        )
        for note in self.notes:
            date_str = note["updated_at"][:10]
            self.note_listbox.insert(tk.END, f"{note['title']}  [{date_str}]")

        self.status_var.set(f"{len(self.notes)} nota/e trovate")

        if self.notes:
            self.note_listbox.selection_set(0)
            self._on_note_select()
        else:
            self._clear_editor()

    # --- Image Gallery ---

    def _load_gallery(self, note_id):
        self._image_refs.clear()
        for w in self.gallery_inner.winfo_children():
            w.destroy()
        self.gallery_labels.clear()
        self.selected_image_index = None

        attachments = db.get_note_attachments(note_id)
        self.gallery_attachments = [a for a in attachments
                                     if image_utils.is_image_file(a["original_name"])]

        if not self.gallery_attachments:
            lbl = ttk.Label(self.gallery_inner, text="Nessuna immagine", style="ImgPanel.TLabel")
            lbl.pack(side=tk.LEFT, padx=20, pady=20)
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

                lbl = tk.Label(frame, image=photo, bg="#f5f5f5", cursor="hand2",
                               borderwidth=2, relief=tk.FLAT)
                lbl.pack()
                tk.Label(frame, text=att["original_name"][:15], bg="#f5f5f5",
                         font=(UI_FONT, 7), fg="#666").pack()

                lbl.bind("<Button-1>", lambda e, idx=i, l=lbl: self._select_gallery_image(idx, l))
                lbl.bind("<Double-Button-1>", lambda e, idx=i: self._open_gallery_image(idx))
                self.gallery_labels.append(lbl)
            except Exception:
                continue

    def _select_gallery_image(self, index, label):
        for lbl in self.gallery_labels:
            lbl.config(relief=tk.FLAT, borderwidth=2)
        label.config(relief=tk.SOLID, borderwidth=2)
        self.selected_image_index = index

    def _open_gallery_image(self, index):
        att = self.gallery_attachments[index]
        path = os.path.join(db.ATTACHMENTS_DIR, att["filename"])
        platform_utils.open_file(path)

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
            messagebox.showerror("Errore", "File non trovato.")
            return

        tool = AnnotationTool(self.root, path)
        if tool.result_path and os.path.exists(tool.result_path):
            db.add_attachment(self.current_note_id, tool.result_path)
            os.remove(tool.result_path)
            self._load_gallery(self.current_note_id)
            self._display_note(self.current_note_id)
            self.status_var.set("Immagine annotata aggiunta")

    # --- Event Handlers ---

    def _on_category_select(self):
        sel = self.cat_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx == 0:
            self.current_category_id = None
        else:
            self.current_category_id = self.categories[idx - 1]["id"]
        self._load_notes()

    def _on_note_select(self):
        sel = self.note_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        note = self.notes[idx]
        self._display_note(note["id"])

    def _on_search(self):
        if self._save_job:
            self.root.after_cancel(self._save_job)
            self._save_job = None
        self._save_current_note()
        self._load_notes()

    def _on_tag_filter(self):
        idx = self.tag_combo.current()
        if idx <= 0:
            self.current_tag_id = None
        else:
            self.current_tag_id = self.all_tags[idx - 1]["id"]
        self._load_notes()

    # --- Editor ---

    def _display_note(self, note_id):
        self.current_note_id = note_id
        note = db.get_note(note_id)
        if not note:
            return

        self.title_var.trace_remove("write", self.title_var.trace_info()[0][1])
        self.title_var.set(note["title"])
        self.title_var.trace_add("write", lambda *_: self._schedule_save())

        self.text_editor.delete("1.0", tk.END)
        self.text_editor.insert("1.0", note["content"] or "")

        created = note["created_at"][:16].replace("T", " ")
        updated = note["updated_at"][:16].replace("T", " ")
        self.meta_label.config(text=f"Creata: {created}   |   Modificata: {updated}")

        tags = db.get_note_tags(note_id)
        if tags:
            tag_str = "Tag: " + ", ".join(f"#{t['name']}" for t in tags)
        else:
            tag_str = "Nessun tag"

        attachments = db.get_note_attachments(note_id)
        att_count = len(attachments)
        if att_count > 0:
            tag_str += f"   |   {att_count} allegato/i"
        self.tags_label.config(text=tag_str)

        self._load_gallery(note_id)

    def _clear_editor(self):
        self.current_note_id = None
        self.title_var.trace_remove("write", self.title_var.trace_info()[0][1])
        self.title_var.set("")
        self.title_var.trace_add("write", lambda *_: self._schedule_save())
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
        title = self.title_var.get().strip()
        content = self.text_editor.get("1.0", tk.END).rstrip("\n")
        if not title:
            return
        db.update_note(self.current_note_id, title=title, content=content)

        sel = self.note_listbox.curselection()
        if sel:
            idx = sel[0]
            date_str = datetime.now().isoformat()[:10]
            self.note_listbox.delete(idx)
            self.note_listbox.insert(idx, f"{title}  [{date_str}]")
            self.note_listbox.selection_set(idx)

        self.status_var.set("Salvato")

    # --- Actions ---

    def _new_note(self):
        categories = db.get_all_categories()
        dlg = NoteDialog(self.root, categories)
        if dlg.result:
            note_id = db.add_note(dlg.result["title"], category_id=dlg.result["category_id"])
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
        if messagebox.askyesno("Conferma", f"Eliminare la nota '{note['title']}'?"):
            db.delete_note(self.current_note_id)
            self.current_note_id = None
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
        cat = None
        for c in self.categories:
            if c["id"] == self.current_category_id:
                cat = c
                break
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
        cat = None
        for c in self.categories:
            if c["id"] == self.current_category_id:
                cat = c
                break
        if not cat:
            return
        if messagebox.askyesno("Conferma", f"Eliminare la categoria '{cat['name']}'?\nLe note non verranno eliminate."):
            db.delete_category(self.current_category_id)
            self.current_category_id = None
            self._load_categories()
            self._load_notes()

    def _manage_tags(self):
        if self.current_note_id is None:
            messagebox.showinfo("Info", "Seleziona una nota prima.")
            return
        TagManagerDialog(self.root, self.current_note_id)
        self._display_note(self.current_note_id)
        self._load_categories()

    def _manage_attachments(self):
        if self.current_note_id is None:
            messagebox.showinfo("Info", "Seleziona una nota prima.")
            return
        AttachmentDialog(self.root, self.current_note_id)
        self._display_note(self.current_note_id)

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
            if full:
                success = platform_utils.take_screenshot(save_path)
            else:
                success = platform_utils.take_screenshot_region(save_path)
        except Exception:
            success = False

        self.root.deiconify()

        if success and os.path.exists(save_path):
            now = datetime.now().isoformat()
            conn = db.get_connection()
            conn.execute(
                "INSERT INTO attachments (note_id, filename, original_name, added_at) VALUES (?, ?, ?, ?)",
                (self.current_note_id, filename, filename, now),
            )
            conn.commit()
            conn.close()
            self._display_note(self.current_note_id)
            self.status_var.set("Screenshot catturato!")
        else:
            if platform_utils.IS_LINUX:
                msg = "Impossibile catturare lo screenshot.\nInstalla: sudo dnf install grim slurp"
            elif platform_utils.IS_WINDOWS:
                msg = "Impossibile catturare lo screenshot.\nVerifica che Pillow sia installato."
            else:
                msg = "Impossibile catturare lo screenshot."
            messagebox.showwarning("Screenshot", msg, parent=self.root)

    def _insert_image(self):
        if self.current_note_id is None:
            messagebox.showinfo("Info", "Crea o seleziona una nota prima.")
            return

        path = filedialog.askopenfilename(
            parent=self.root,
            title="Seleziona immagine",
            filetypes=[
                ("Immagini", "*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.webp"),
                ("Tutti i file", "*.*"),
            ],
        )
        if path:
            db.add_attachment(self.current_note_id, path)
            self._display_note(self.current_note_id)
            self.status_var.set(f"Immagine '{os.path.basename(path)}' aggiunta")

    # --- Auto-Update ---

    def _check_updates_silent(self):
        """Controlla aggiornamenti in background all'avvio, senza disturbare."""
        def check():
            result = updater.check_for_updates()
            if result:
                self.root.after(0, lambda: self._notify_update(result))

        threading.Thread(target=check, daemon=True).start()

    def _check_updates(self):
        """Controlla aggiornamenti manualmente (dal menu)."""
        self.status_var.set("Controllo aggiornamenti...")

        def check():
            result = updater.check_for_updates()
            self.root.after(0, lambda: self._handle_update_result(result, manual=True))

        threading.Thread(target=check, daemon=True).start()

    def _notify_update(self, update_info):
        """Mostra notifica discreta nella status bar."""
        tag, url, notes = update_info
        self.status_var.set(f"Aggiornamento disponibile: {tag} (Aiuto > Controlla aggiornamenti)")

    def _handle_update_result(self, result, manual=False):
        if result is None:
            if manual:
                self.status_var.set("Nessun aggiornamento disponibile")
                messagebox.showinfo("Aggiornamenti", f"MyNotes v{VERSION} \u00e8 aggiornato!")
            return

        tag, url, notes = result
        msg = f"Nuova versione disponibile: {tag}\n(Attuale: v{VERSION})\n"
        if notes:
            # Mostra solo le prime righe delle note
            short_notes = "\n".join(notes.split("\n")[:5])
            msg += f"\n{short_notes}\n"
        msg += "\nVuoi aggiornare ora?"

        if messagebox.askyesno("Aggiornamento disponibile", msg):
            self._do_update(url)

    def _do_update(self, download_url):
        """Esegue il download e l'aggiornamento."""
        # Progress dialog
        progress_win = tk.Toplevel(self.root)
        progress_win.title("Aggiornamento MyNotes")
        progress_win.geometry("400x120")
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
            def update():
                status_label.config(text=msg)
                if pct >= 0:
                    progress_bar["value"] = pct
            self.root.after(0, update)

        def do_download():
            success = updater.download_and_apply_update(download_url, on_progress)

            def finish():
                progress_win.destroy()
                if success:
                    if platform_utils.IS_WINDOWS:
                        messagebox.showinfo(
                            "Aggiornamento",
                            "Aggiornamento scaricato!\n"
                            "L'app si chiuder\u00e0 e si riavvier\u00e0 automaticamente."
                        )
                        self.root.quit()
                    else:
                        restart = messagebox.askyesno(
                            "Aggiornamento completato",
                            "Aggiornamento applicato con successo!\n"
                            "Vuoi riavviare MyNotes ora?"
                        )
                        if restart:
                            import subprocess
                            cmd = updater.get_restart_command()
                            subprocess.Popen(cmd)
                            self.root.quit()
                        else:
                            self.status_var.set("Aggiornamento applicato. Riavvia per usare la nuova versione.")
                else:
                    messagebox.showerror(
                        "Errore",
                        "Aggiornamento fallito.\nRiprova pi\u00f9 tardi o scarica manualmente da GitHub."
                    )

            self.root.after(0, finish)

        threading.Thread(target=do_download, daemon=True).start()
