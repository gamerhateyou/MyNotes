"""Finestra dedicata per editing di una nota singola."""

import os
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

import database as db
import crypto_utils
import image_utils
import platform_utils
import audio_utils
from gui.constants import UI_FONT, MONO_FONT, AUTO_SAVE_MS, VERSION_SAVE_EVERY
from annotator import AnnotationTool
from dialogs import (TagManagerDialog, AttachmentDialog,
                     VersionHistoryDialog, PasswordDialog, AudioRecordDialog)


class NoteWindow(tk.Toplevel):
    """Finestra indipendente per editing di una nota."""

    def __init__(self, parent_app, note_id):
        super().__init__(parent_app.root)
        self.app = parent_app
        self.note_id = note_id

        # Proprio stato indipendente
        self._save_job = None
        self._image_refs = []
        self._decrypted_cache = {}
        self._version_counter = 0
        self.gallery_labels = []
        self.selected_image_index = None
        self.gallery_attachments = []
        self._gallery_load_id = None

        self.geometry("900x650")
        self.minsize(700, 450)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._display_note()

    # ─── UI ────────────────────────────────────────────────────

    def _build_ui(self):
        # Toolbar
        toolbar = ttk.Frame(self, style="Toolbar.TFrame", padding=5)
        toolbar.pack(fill=tk.X)

        # Dropdown "Nota"
        note_mb = ttk.Menubutton(toolbar, text="Nota \u25be")
        note_menu = tk.Menu(note_mb, tearoff=0)
        note_menu.add_command(label="Fissa/Sgancia", command=self.toggle_pin)
        note_menu.add_command(label="Preferita", command=self.toggle_favorite)
        note_menu.add_separator()
        note_menu.add_command(label="Tag...", command=self.manage_tags)
        note_menu.add_command(label="Allegati...", command=self.manage_attachments)
        note_menu.add_command(label="Cronologia versioni...", command=self.show_versions)
        note_menu.add_separator()
        note_menu.add_command(label="Cripta nota...", command=self.encrypt_note)
        note_menu.add_command(label="Decripta nota...", command=self.decrypt_note)
        note_mb["menu"] = note_menu
        note_mb.pack(side=tk.LEFT, padx=2)

        # Dropdown "Inserisci"
        ins_mb = ttk.Menubutton(toolbar, text="Inserisci \u25be")
        ins_menu = tk.Menu(ins_mb, tearoff=0)
        ins_menu.add_command(label="Screenshot intero", command=self.take_screenshot)
        ins_menu.add_command(label="Screenshot regione", command=self.take_screenshot_region)
        ins_menu.add_command(label="Immagine...", command=self.insert_image)
        ins_menu.add_separator()
        ins_menu.add_command(label="Checklist", command=self.insert_checklist)
        ins_menu.add_separator()
        ins_menu.add_command(label="Registra audio...", command=self.record_audio)
        ins_menu.add_command(label="Importa audio...", command=self.import_audio)
        ins_mb["menu"] = ins_menu
        ins_mb.pack(side=tk.LEFT, padx=2)

        # Title
        title_frame = ttk.Frame(self, padding=(10, 8))
        title_frame.pack(fill=tk.X)
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(title_frame, textvariable=self.title_var,
                                     font=(UI_FONT, 14, "bold"))
        self.title_entry.pack(fill=tk.X)
        self.title_var.trace_add("write", lambda *_: self.schedule_save())

        # Meta + Tags
        self.meta_label = ttk.Label(self, text="", style="Meta.TLabel", padding=(12, 0))
        self.meta_label.pack(fill=tk.X)
        self.tags_label = ttk.Label(self, text="", style="Meta.TLabel", padding=(12, 2))
        self.tags_label.pack(fill=tk.X)

        # Editor + Gallery pane
        editor_pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        editor_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        # Text editor
        text_frame = ttk.Frame(editor_pane)
        editor_pane.add(text_frame, weight=3)
        self.text_editor = tk.Text(
            text_frame, font=(MONO_FONT, 11), wrap=tk.WORD,
            undo=True, borderwidth=1, relief=tk.SOLID, padx=8, pady=8
        )
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL,
                                  command=self.text_editor.yview)
        self.text_editor.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_editor.pack(fill=tk.BOTH, expand=True)
        self.text_editor.bind("<KeyRelease>", lambda e: self.schedule_save())
        self.text_editor.bind("<Button-1>", lambda e: self.on_text_click(e))

        self.text_editor.tag_configure("checkbox_done", overstrike=True, foreground="#888888")
        self.text_editor.tag_configure("checkbox_open", foreground="#333333")
        self.text_editor.tag_configure("audio_marker", foreground="#1a73e8", background="#e8f0fe")

        # Gallery
        gallery_frame = ttk.Frame(editor_pane)
        editor_pane.add(gallery_frame, weight=1)
        gallery_header = ttk.Frame(gallery_frame)
        gallery_header.pack(fill=tk.X)
        ttk.Label(gallery_header, text="Immagini allegate",
                  style="ImgPanel.TLabel").pack(side=tk.LEFT, padx=5)
        ttk.Button(gallery_header, text="Annota",
                   command=self.annotate_selected).pack(side=tk.RIGHT, padx=2)
        ttk.Button(gallery_header, text="Apri",
                   command=self.open_selected).pack(side=tk.RIGHT, padx=2)
        ttk.Button(gallery_header, text="Rimuovi",
                   command=self.remove_selected).pack(side=tk.RIGHT, padx=2)

        self.gallery_canvas = tk.Canvas(gallery_frame, height=120, bg="#f5f5f5",
                                        highlightthickness=1, highlightbackground="#cccccc")
        gallery_scroll = ttk.Scrollbar(gallery_frame, orient=tk.HORIZONTAL,
                                       command=self.gallery_canvas.xview)
        self.gallery_canvas.configure(xscrollcommand=gallery_scroll.set)
        gallery_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.gallery_canvas.pack(fill=tk.BOTH, expand=True)
        self.gallery_inner = ttk.Frame(self.gallery_canvas)
        self.gallery_canvas.create_window((0, 0), window=self.gallery_inner, anchor=tk.NW)
        self.gallery_inner.bind(
            "<Configure>",
            lambda e: self.gallery_canvas.configure(
                scrollregion=self.gallery_canvas.bbox("all")))

        # Status bar
        self.status_var = tk.StringVar(value="Pronto")
        ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN,
                  anchor=tk.W, padding=(8, 3)).pack(fill=tk.X, side=tk.BOTTOM)

    # ─── Display ───────────────────────────────────────────────

    def _display_note(self):
        note = db.get_note(self.note_id)
        if not note:
            self.title("Nota non trovata")
            return

        self.title(f"{note['title']} - MyNotes")

        # Title (disable trace, set, re-enable)
        traces = self.title_var.trace_info()
        for t in traces:
            self.title_var.trace_remove(t[0], t[1])
        self.title_var.set(note["title"])
        self.title_var.trace_add("write", lambda *_: self.schedule_save())

        # Editor content
        self.text_editor.config(state=tk.NORMAL)
        self.text_editor.delete("1.0", tk.END)

        if note["is_encrypted"]:
            if self.note_id in self._decrypted_cache:
                self.text_editor.insert("1.0", self._decrypted_cache[self.note_id])
            else:
                self.text_editor.insert("1.0",
                                        "[Nota criptata - usa Nota > Decripta nota...]")
                self.text_editor.config(state=tk.DISABLED)
        else:
            self.text_editor.insert("1.0", note["content"] or "")
            self._apply_checklist_formatting()
            self._apply_audio_formatting()

        # Meta
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

        # Tags
        tags = db.get_note_tags(self.note_id)
        tag_str = ("Tag: " + ", ".join(f"#{t['name']}" for t in tags)
                   if tags else "Nessun tag")
        att_count = len(db.get_note_attachments(self.note_id))
        if att_count > 0:
            tag_str += f"  |  {att_count} allegato/i"
        self.tags_label.config(text=tag_str)

        self._load_gallery()

    # ─── Auto-save ─────────────────────────────────────────────

    def schedule_save(self):
        if self._save_job:
            self.after_cancel(self._save_job)
        self._save_job = self.after(AUTO_SAVE_MS, self.save_current)

    def save_current(self):
        self._save_job = None
        if self.text_editor["state"] == "disabled":
            return
        note = db.get_note(self.note_id)
        if not note:
            return
        if note["is_encrypted"] and self.note_id not in self._decrypted_cache:
            return

        title = self.title_var.get().strip()
        content = self.text_editor.get("1.0", tk.END).rstrip("\n")
        if not title:
            return

        if not note["is_encrypted"]:
            self._version_counter += 1
            if self._version_counter >= VERSION_SAVE_EVERY:
                self._version_counter = 0
                db.save_version(self.note_id, title, content)

        if note["is_encrypted"] and self.note_id in self._decrypted_cache:
            self._decrypted_cache[self.note_id] = content
        else:
            db.update_note(self.note_id, title=title, content=content)

        self.title(f"{title} - MyNotes")
        self.status_var.set("Salvato")

    # ─── Checklist / Audio formatting ──────────────────────────

    def _apply_checklist_formatting(self):
        editor = self.text_editor
        editor.tag_remove("checkbox_done", "1.0", tk.END)
        editor.tag_remove("checkbox_open", "1.0", tk.END)
        content = editor.get("1.0", tk.END)
        for i, line in enumerate(content.split("\n"), 1):
            if line.strip().startswith("[x]"):
                editor.tag_add("checkbox_done", f"{i}.0", f"{i}.end")
            elif line.strip().startswith("[ ]"):
                editor.tag_add("checkbox_open", f"{i}.0", f"{i}.end")

    def _apply_audio_formatting(self):
        editor = self.text_editor
        editor.tag_remove("audio_marker", "1.0", tk.END)
        content = editor.get("1.0", tk.END)
        pattern = re.compile(r"\[♪:[^\]]+\]")
        for i, line in enumerate(content.split("\n"), 1):
            for m in pattern.finditer(line):
                editor.tag_add("audio_marker", f"{i}.{m.start()}", f"{i}.{m.end()}")

    def insert_checklist(self):
        self.text_editor.insert(tk.INSERT,
                                "\n[ ] Elemento da fare\n[ ] Altro elemento\n"
                                "[x] Elemento completato\n")
        self._apply_checklist_formatting()

    def _insert_audio_marker(self, att_filename, description):
        desc = description or "audio"
        marker = f"\n[♪:{att_filename} {desc}]\n"
        self.text_editor.insert(tk.INSERT, marker)
        self._apply_audio_formatting()
        self._apply_checklist_formatting()
        self.schedule_save()

    def on_text_click(self, event):
        editor = self.text_editor
        index = editor.index(f"@{event.x},{event.y}")
        line_num = int(index.split(".")[0])
        line = editor.get(f"{line_num}.0", f"{line_num}.end")
        stripped = line.lstrip()

        # Audio marker click
        audio_match = re.search(r"\[♪:(\S+)", line)
        if audio_match:
            col = int(index.split(".")[1])
            marker_match = re.search(r"\[♪:[^\]]+\]", line)
            if marker_match and marker_match.start() <= col <= marker_match.end():
                filename = audio_match.group(1)
                path = os.path.join(db.ATTACHMENTS_DIR, filename)
                if os.path.exists(path):
                    platform_utils.open_file(path)
                else:
                    messagebox.showwarning("Audio", f"File non trovato:\n{filename}",
                                           parent=self)
                return

        if stripped.startswith("[ ]"):
            offset = len(line) - len(stripped)
            editor.delete(f"{line_num}.{offset}", f"{line_num}.{offset + 3}")
            editor.insert(f"{line_num}.{offset}", "[x]")
            self._apply_checklist_formatting()
            self.schedule_save()
        elif stripped.startswith("[x]"):
            offset = len(line) - len(stripped)
            editor.delete(f"{line_num}.{offset}", f"{line_num}.{offset + 3}")
            editor.insert(f"{line_num}.{offset}", "[ ]")
            self._apply_checklist_formatting()
            self.schedule_save()

    # ─── Gallery ───────────────────────────────────────────────

    def _load_gallery(self):
        self._image_refs.clear()
        for w in self.gallery_inner.winfo_children():
            w.destroy()
        self.gallery_labels.clear()
        self.selected_image_index = None
        self._gallery_load_id = self.note_id

        attachments = db.get_note_attachments(self.note_id)
        self.gallery_attachments = [
            a for a in attachments if image_utils.is_image_file(a["original_name"])]

        if not self.gallery_attachments:
            ttk.Label(self.gallery_inner, text="Nessuna immagine",
                      style="ImgPanel.TLabel").pack(side=tk.LEFT, padx=20, pady=20)
            return

        items = []
        for i, att in enumerate(self.gallery_attachments):
            path = os.path.join(db.ATTACHMENTS_DIR, att["filename"])
            if not os.path.exists(path):
                items.append((i, att, path, None))
                continue
            frame = tk.Frame(self.gallery_inner, bg="#f5f5f5", padx=4, pady=4)
            frame.pack(side=tk.LEFT, padx=3, pady=3)
            lbl = tk.Label(frame, text="...", width=12, height=5, bg="#e0e0e0",
                           cursor="hand2", borderwidth=2, relief=tk.FLAT)
            lbl.pack()
            tk.Label(frame, text=att["original_name"][:15], bg="#f5f5f5",
                     font=(UI_FONT, 7), fg="#666").pack()
            lbl.bind("<Button-1>", lambda e, idx=i, l=lbl: self._select_image(idx, l))
            lbl.bind("<Double-Button-1>", lambda e, idx=i: self._open_image(idx))
            self.gallery_labels.append(lbl)
            items.append((i, att, path, lbl))

        def _load_thumbs():
            for i, att, path, lbl in items:
                if self._gallery_load_id != self.note_id:
                    return
                if lbl is None:
                    continue
                try:
                    photo = image_utils.load_image_as_photo(path, max_width=100,
                                                            max_height=100)
                    self.after(0, lambda p=photo, l=lbl: self._set_thumb(p, l))
                except Exception:
                    continue

        threading.Thread(target=_load_thumbs, daemon=True).start()

    def _set_thumb(self, photo, label):
        self._image_refs.append(photo)
        label.config(image=photo, text="", width=0, height=0)

    def _select_image(self, index, label):
        for lbl in self.gallery_labels:
            lbl.config(relief=tk.FLAT)
        label.config(relief=tk.SOLID)
        self.selected_image_index = index

    def _open_image(self, index):
        att = self.gallery_attachments[index]
        platform_utils.open_file(os.path.join(db.ATTACHMENTS_DIR, att["filename"]))

    def open_selected(self):
        if self.selected_image_index is not None:
            self._open_image(self.selected_image_index)

    def remove_selected(self):
        if self.selected_image_index is None:
            return
        att = self.gallery_attachments[self.selected_image_index]
        if messagebox.askyesno("Conferma", f"Rimuovere '{att['original_name']}'?",
                               parent=self):
            db.delete_attachment(att["id"])
            self._display_note()

    def annotate_selected(self):
        if self.selected_image_index is None:
            messagebox.showinfo("Info", "Seleziona un'immagine dalla galleria.",
                                parent=self)
            return
        att = self.gallery_attachments[self.selected_image_index]
        path = os.path.join(db.ATTACHMENTS_DIR, att["filename"])
        if not os.path.exists(path):
            return
        tool = AnnotationTool(self, path)
        if tool.result_path and os.path.exists(tool.result_path):
            db.add_attachment(self.note_id, tool.result_path)
            os.remove(tool.result_path)
            self._display_note()

    # ─── Media ─────────────────────────────────────────────────

    def take_screenshot(self):
        self.withdraw()
        self.after(500, lambda: self._do_screenshot(full=True))

    def take_screenshot_region(self):
        self.withdraw()
        self.after(500, lambda: self._do_screenshot(full=False))

    def _do_screenshot(self, full=True):
        import uuid
        filename = f"screenshot_{uuid.uuid4().hex[:8]}.png"
        save_path = os.path.join(db.ATTACHMENTS_DIR, filename)
        try:
            success = (platform_utils.take_screenshot(save_path) if full
                       else platform_utils.take_screenshot_region(save_path))
        except Exception:
            success = False
        self.deiconify()
        if success and os.path.exists(save_path):
            now = datetime.now().isoformat()
            with db._connect() as conn:
                conn.execute(
                    "INSERT INTO attachments (note_id, filename, original_name, added_at) "
                    "VALUES (?, ?, ?, ?)",
                    (self.note_id, filename, filename, now))
                conn.commit()
            self._display_note()
            self.status_var.set("Screenshot catturato!")
        else:
            msg = "Impossibile catturare lo screenshot.\n"
            if platform_utils.IS_LINUX:
                msg += "Installa: sudo dnf install grim slurp"
            messagebox.showwarning("Screenshot", msg, parent=self)

    def insert_image(self):
        path = filedialog.askopenfilename(
            parent=self, title="Seleziona immagine",
            filetypes=[("Immagini", "*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.webp"),
                       ("Tutti", "*.*")])
        if path:
            db.add_attachment(self.note_id, path)
            self._display_note()
            self.status_var.set("Immagine aggiunta")

    def record_audio(self):
        dlg = AudioRecordDialog(self, mode="record")
        if dlg.result is None:
            return
        temp_path = dlg.result["path"]
        description = dlg.result["description"]
        att_filename = db.add_attachment(self.note_id, temp_path)
        try:
            os.remove(temp_path)
        except OSError:
            pass
        self._insert_audio_marker(att_filename, description)
        self._display_note()
        self.status_var.set("Audio registrato")

    def import_audio(self):
        path = filedialog.askopenfilename(
            parent=self, title="Seleziona file audio",
            filetypes=[("Audio", "*.mp3 *.wav *.ogg *.m4a *.flac *.aac *.wma"),
                       ("Tutti", "*.*")])
        if not path:
            return
        dlg = AudioRecordDialog(self, mode="describe", audio_path=path)
        if dlg.result is None:
            return
        description = dlg.result["description"]
        att_filename = db.add_attachment(self.note_id, path)
        self._insert_audio_marker(att_filename, description)
        self._display_note()
        self.status_var.set("Audio importato")

    # ─── Note Actions ──────────────────────────────────────────

    def toggle_pin(self):
        db.toggle_pin(self.note_id)
        self._display_note()
        self.app.notes_ctl.load_notes()

    def toggle_favorite(self):
        db.toggle_favorite(self.note_id)
        self._display_note()
        self.app.notes_ctl.load_notes()

    def manage_tags(self):
        TagManagerDialog(self, self.note_id)
        self._display_note()
        self.app.notes_ctl.load_categories()

    def manage_attachments(self):
        AttachmentDialog(self, self.note_id)
        self._display_note()

    def show_versions(self):
        note = db.get_note(self.note_id)
        if not note:
            return
        if note["is_encrypted"]:
            messagebox.showinfo("Info",
                                "La cronologia versioni non e' disponibile per le note criptate.",
                                parent=self)
            return
        content = self.text_editor.get("1.0", tk.END).rstrip("\n")
        db.save_version(self.note_id, note["title"], content)
        dlg = VersionHistoryDialog(self, self.note_id)
        if dlg.result:
            self._display_note()

    def encrypt_note(self):
        note = db.get_note(self.note_id)
        if not note:
            return
        if note["is_encrypted"]:
            messagebox.showinfo("Info", "La nota e' gia' criptata.", parent=self)
            return
        dlg = PasswordDialog(self, title="Cripta nota", confirm=True)
        if dlg.result:
            content = self.text_editor.get("1.0", tk.END).rstrip("\n")
            encrypted = crypto_utils.encrypt(content, dlg.result)
            db.set_note_encrypted(self.note_id, encrypted, True)
            db.delete_note_versions(self.note_id)
            self._decrypted_cache.pop(self.note_id, None)
            self._display_note()
            self.status_var.set("Nota criptata")

    def decrypt_note(self):
        note = db.get_note(self.note_id)
        if not note:
            return
        if not note["is_encrypted"]:
            messagebox.showinfo("Info", "La nota non e' criptata.", parent=self)
            return
        dlg = PasswordDialog(self, title="Decripta nota")
        if dlg.result:
            decrypted = crypto_utils.decrypt(note["content"], dlg.result)
            if decrypted is None:
                messagebox.showerror("Errore", "Password errata.", parent=self)
                return
            action = messagebox.askyesnocancel(
                "Decripta",
                "Nota decriptata!\n\nSi = Rimuovi crittografia permanentemente\n"
                "No = Visualizza solo (resta criptata)\nAnnulla = Chiudi",
                parent=self)
            if action is True:
                db.set_note_encrypted(self.note_id, decrypted, False)
                self._decrypted_cache.pop(self.note_id, None)
            elif action is False:
                self._decrypted_cache[self.note_id] = decrypted
            else:
                return
            self._display_note()

    # ─── Lifecycle ─────────────────────────────────────────────

    def _on_close(self):
        self.save_current()
        self.app._detached_windows.pop(self.note_id, None)
        self.app.notes_ctl.load_notes()
        self.destroy()
