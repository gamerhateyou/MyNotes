"""Screenshots, image gallery, annotations, audio."""

import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import database as db
import image_utils
import platform_utils
import audio_utils
from gui.constants import UI_FONT
from annotator import AnnotationTool
from dialogs import AudioRecordDialog


class MediaController:
    def __init__(self, app):
        self.app = app

    # --- Gallery ---

    def load_gallery(self, note_id):
        app = self.app
        app._image_refs.clear()
        for w in app.gallery_inner.winfo_children():
            w.destroy()
        app.gallery_labels.clear()
        app.selected_image_index = None
        self._gallery_load_id = note_id

        attachments = db.get_note_attachments(note_id)
        app.gallery_attachments = [a for a in attachments if image_utils.is_image_file(a["original_name"])]

        if not app.gallery_attachments:
            ttk.Label(app.gallery_inner, text="Nessuna immagine", style="ImgPanel.TLabel").pack(side=tk.LEFT, padx=20, pady=20)
            return

        # Prepara placeholder e carica thumbnail in background
        items = []
        for i, att in enumerate(app.gallery_attachments):
            path = os.path.join(db.ATTACHMENTS_DIR, att["filename"])
            if not os.path.exists(path):
                items.append((i, att, path, None))
                continue
            frame = tk.Frame(app.gallery_inner, bg="#f5f5f5", padx=4, pady=4)
            frame.pack(side=tk.LEFT, padx=3, pady=3)
            lbl = tk.Label(frame, text="...", width=12, height=5, bg="#e0e0e0", cursor="hand2", borderwidth=2, relief=tk.FLAT)
            lbl.pack()
            tk.Label(frame, text=att["original_name"][:15], bg="#f5f5f5", font=(UI_FONT, 7), fg="#666").pack()
            lbl.bind("<Button-1>", lambda e, idx=i, l=lbl: self._select_image(idx, l))
            lbl.bind("<Double-Button-1>", lambda e, idx=i: self._open_image(idx))
            lbl.bind("<Button-3>", lambda e, idx=i, l=lbl: self._show_gallery_context_menu(e, idx, l))
            app.gallery_labels.append(lbl)
            items.append((i, att, path, lbl))

        def _load_thumbs():
            for i, att, path, lbl in items:
                if self._gallery_load_id != note_id:
                    return  # Nota cambiata, annulla
                if lbl is None:
                    continue
                try:
                    photo = image_utils.load_image_as_photo(path, max_width=100, max_height=100)
                    app.root.after(0, lambda p=photo, l=lbl: self._set_thumb(p, l))
                except Exception:
                    continue

        threading.Thread(target=_load_thumbs, daemon=True).start()

    def _set_thumb(self, photo, label):
        """Aggiorna thumbnail nella gallery dal thread principale."""
        self.app._image_refs.append(photo)
        label.config(image=photo, text="", width=0, height=0)

    def _select_image(self, index, label):
        for lbl in self.app.gallery_labels:
            lbl.config(relief=tk.FLAT)
        label.config(relief=tk.SOLID)
        self.app.selected_image_index = index

    def _show_gallery_context_menu(self, event, index, label):
        self._select_image(index, label)
        menu = tk.Menu(self.app.root, tearoff=0)
        menu.add_command(label="Apri", command=lambda: self._open_image(index))
        menu.add_command(label="Annota", command=self.annotate_selected)
        menu.add_separator()
        menu.add_command(label="Rimuovi", command=self.remove_selected)
        menu.tk_popup(event.x_root, event.y_root)

    def _open_image(self, index):
        att = self.app.gallery_attachments[index]
        platform_utils.open_file(os.path.join(db.ATTACHMENTS_DIR, att["filename"]))

    def open_selected(self):
        if self.app.selected_image_index is not None:
            self._open_image(self.app.selected_image_index)

    def remove_selected(self):
        app = self.app
        if app.selected_image_index is None:
            return
        att = app.gallery_attachments[app.selected_image_index]
        if messagebox.askyesno("Conferma", f"Rimuovere '{att['original_name']}'?"):
            db.delete_attachment(att["id"])
            if app.current_note_id:
                self.load_gallery(app.current_note_id)
                app.notes_ctl.display_note(app.current_note_id)

    def annotate_selected(self):
        app = self.app
        if app.selected_image_index is None:
            messagebox.showinfo("Info", "Seleziona un'immagine dalla galleria.")
            return
        att = app.gallery_attachments[app.selected_image_index]
        path = os.path.join(db.ATTACHMENTS_DIR, att["filename"])
        if not os.path.exists(path):
            return
        tool = AnnotationTool(app.root, path)
        if tool.result_path and os.path.exists(tool.result_path):
            db.add_attachment(app.current_note_id, tool.result_path)
            os.remove(tool.result_path)
            self.load_gallery(app.current_note_id)
            app.notes_ctl.display_note(app.current_note_id)

    # --- Screenshots ---

    def take_screenshot(self):
        if self.app.current_note_id is None:
            messagebox.showinfo("Info", "Crea o seleziona una nota prima.")
            return
        self.app.root.withdraw()
        self.app.root.after(500, lambda: self._do_screenshot(full=True))

    def take_screenshot_region(self):
        if self.app.current_note_id is None:
            messagebox.showinfo("Info", "Crea o seleziona una nota prima.")
            return
        self.app.root.withdraw()
        self.app.root.after(500, lambda: self._do_screenshot(full=False))

    def _do_screenshot(self, full=True):
        import uuid
        app = self.app
        filename = f"screenshot_{uuid.uuid4().hex[:8]}.png"
        save_path = os.path.join(db.ATTACHMENTS_DIR, filename)
        try:
            success = platform_utils.take_screenshot(save_path) if full else platform_utils.take_screenshot_region(save_path)
        except Exception:
            success = False
        app.root.deiconify()
        if success and os.path.exists(save_path):
            now = datetime.now().isoformat()
            with db._connect() as conn:
                conn.execute(
                    "INSERT INTO attachments (note_id, filename, original_name, added_at) VALUES (?, ?, ?, ?)",
                    (app.current_note_id, filename, filename, now))
                conn.commit()
            app.notes_ctl.display_note(app.current_note_id)
            app.status_var.set("Screenshot catturato!")
        else:
            msg = "Impossibile catturare lo screenshot.\n"
            if platform_utils.IS_LINUX:
                msg += "Installa: sudo dnf install grim slurp"
            messagebox.showwarning("Screenshot", msg, parent=app.root)

    def insert_image(self):
        app = self.app
        if app.current_note_id is None:
            return
        path = filedialog.askopenfilename(
            parent=app.root, title="Seleziona immagine",
            filetypes=[("Immagini", "*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.webp"), ("Tutti", "*.*")])
        if path:
            db.add_attachment(app.current_note_id, path)
            app.notes_ctl.display_note(app.current_note_id)
            app.status_var.set(f"Immagine aggiunta")

    # --- Audio ---

    def record_audio(self):
        app = self.app
        if app.current_note_id is None:
            messagebox.showinfo("Info", "Crea o seleziona una nota prima.")
            return

        dlg = AudioRecordDialog(app.root, mode="record")
        if dlg.result is None:
            return

        temp_path = dlg.result["path"]
        description = dlg.result["description"]

        att_filename = db.add_attachment(app.current_note_id, temp_path)
        # Remove temp file
        try:
            os.remove(temp_path)
        except OSError:
            pass

        app.notes_ctl.insert_audio_marker(att_filename, description)
        app.notes_ctl.display_note(app.current_note_id)
        app.status_var.set("Audio registrato")

    def import_audio(self):
        app = self.app
        if app.current_note_id is None:
            messagebox.showinfo("Info", "Crea o seleziona una nota prima.")
            return

        path = filedialog.askopenfilename(
            parent=app.root, title="Seleziona file audio",
            filetypes=[("Audio", "*.mp3 *.wav *.ogg *.m4a *.flac *.aac *.wma"), ("Tutti", "*.*")])
        if not path:
            return

        dlg = AudioRecordDialog(app.root, mode="describe", audio_path=path)
        if dlg.result is None:
            return

        description = dlg.result["description"]
        att_filename = db.add_attachment(app.current_note_id, path)

        app.notes_ctl.insert_audio_marker(att_filename, description)
        app.notes_ctl.display_note(app.current_note_id)
        app.status_var.set("Audio importato")
