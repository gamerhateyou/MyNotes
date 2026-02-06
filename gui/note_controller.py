"""Note CRUD, categories, tags, encryption, checklist."""

import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import database as db
import crypto_utils
from gui.constants import AUTO_SAVE_MS, VERSION_SAVE_EVERY
from dialogs import (CategoryDialog, NoteDialog, TagManagerDialog, AttachmentDialog,
                     VersionHistoryDialog, PasswordDialog)


class NoteController:
    def __init__(self, app):
        self.app = app

    # --- Data Loading ---

    def load_categories(self):
        app = self.app
        app.cat_listbox.delete(0, tk.END)
        app.cat_listbox.insert(tk.END, "  Tutte le note")
        app.cat_listbox.insert(tk.END, "  Preferite")

        app.categories = db.get_all_categories()
        for cat in app.categories:
            app.cat_listbox.insert(tk.END, f"  {cat['name']}")

        trash_count = db.get_trash_count()
        app.cat_listbox.insert(tk.END, f"  Cestino ({trash_count})")

        last_idx = app.cat_listbox.size() - 1
        app.cat_listbox.itemconfig(last_idx, fg="#aa4444")
        app.cat_listbox.itemconfig(1, fg="#e6a817")
        app.cat_listbox.selection_set(0)

        all_tags = db.get_all_tags()
        tag_names = ["(Tutti)"] + [t["name"] for t in all_tags]
        app.tag_combo["values"] = tag_names
        app.tag_combo.current(0)
        app.all_tags = all_tags

    def load_notes(self):
        app = self.app
        app.note_listbox.delete(0, tk.END)
        search = app.search_var.get().strip() or None

        app.notes = db.get_all_notes(
            category_id=app.current_category_id,
            tag_id=app.current_tag_id,
            search_query=search,
            show_deleted=app.show_trash,
            favorites_only=app.show_favorites,
        )

        for note in app.notes:
            date_str = note["updated_at"][:10]
            prefix = ""
            if note["is_pinned"]:
                prefix += "[P] "
            if note["is_favorite"]:
                prefix += "[*] "
            if note["is_encrypted"]:
                prefix += "[E] "
            app.note_listbox.insert(tk.END, f"{prefix}{note['title']}  [{date_str}]")

        header = "Cestino" if app.show_trash else ("Preferite" if app.show_favorites else "Note")
        app.list_header.config(text=f"{header} ({len(app.notes)})")
        app.status_var.set(f"{len(app.notes)} nota/e")

        if app.notes:
            app.note_listbox.selection_set(0)
            self.on_note_select()
        else:
            self._clear_editor()

    # --- Event Handlers ---

    def on_category_select(self):
        app = self.app
        sel = app.cat_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        app.show_trash = False
        app.show_favorites = False
        app.current_category_id = None

        if idx == 0:
            pass
        elif idx == 1:
            app.show_favorites = True
        elif idx == app.cat_listbox.size() - 1:
            app.show_trash = True
        else:
            app.current_category_id = app.categories[idx - 2]["id"]
        self.load_notes()

    def on_note_select(self):
        sel = self.app.note_listbox.curselection()
        if not sel:
            return
        note = self.app.notes[sel[0]]
        self.display_note(note["id"])

    def on_search(self):
        app = self.app
        if app._save_job:
            app.root.after_cancel(app._save_job)
            app._save_job = None
        self.save_current()
        self.load_notes()

    def on_tag_filter(self):
        app = self.app
        idx = app.tag_combo.current()
        app.current_tag_id = None if idx <= 0 else app.all_tags[idx - 1]["id"]
        self.load_notes()

    # --- Editor ---

    def display_note(self, note_id):
        app = self.app
        self.save_current()
        app.current_note_id = note_id
        # Clear decrypted cache for previous note
        prev_ids = [nid for nid in app._decrypted_cache if nid != note_id]
        for nid in prev_ids:
            del app._decrypted_cache[nid]

        note = db.get_note(note_id)
        if not note:
            return

        app.title_var.trace_remove("write", app.title_var.trace_info()[0][1])
        app.title_var.set(note["title"])
        app.title_var.trace_add("write", lambda *_: self.schedule_save())

        app.text_editor.delete("1.0", tk.END)

        if note["is_encrypted"]:
            if note_id in app._decrypted_cache:
                app.text_editor.insert("1.0", app._decrypted_cache[note_id])
            else:
                app.text_editor.insert("1.0", "[Nota criptata - usa Nota > Decripta nota...]")
                app.text_editor.config(state=tk.DISABLED)
        else:
            app.text_editor.config(state=tk.NORMAL)
            app.text_editor.insert("1.0", note["content"] or "")
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
        app.meta_label.config(text=meta)

        tags = db.get_note_tags(note_id)
        tag_str = "Tag: " + ", ".join(f"#{t['name']}" for t in tags) if tags else "Nessun tag"
        att_count = len(db.get_note_attachments(note_id))
        if att_count > 0:
            tag_str += f"  |  {att_count} allegato/i"
        app.tags_label.config(text=tag_str)

        app.media_ctl.load_gallery(note_id)

    def _clear_editor(self):
        app = self.app
        app.current_note_id = None
        app.title_var.trace_remove("write", app.title_var.trace_info()[0][1])
        app.title_var.set("")
        app.title_var.trace_add("write", lambda *_: self.schedule_save())
        app.text_editor.config(state=tk.NORMAL)
        app.text_editor.delete("1.0", tk.END)
        app.meta_label.config(text="")
        app.tags_label.config(text="")
        app._image_refs.clear()
        for w in app.gallery_inner.winfo_children():
            w.destroy()

    def schedule_save(self):
        app = self.app
        if app._save_job:
            app.root.after_cancel(app._save_job)
        app._save_job = app.root.after(AUTO_SAVE_MS, self.save_current)

    def save_current(self):
        app = self.app
        app._save_job = None
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if not note or note["is_encrypted"] and app.current_note_id not in app._decrypted_cache:
            return

        title = app.title_var.get().strip()
        content = app.text_editor.get("1.0", tk.END).rstrip("\n")
        if not title:
            return

        # Don't save plaintext versions for encrypted notes
        if not note["is_encrypted"]:
            app._version_counter += 1
            if app._version_counter >= VERSION_SAVE_EVERY:
                app._version_counter = 0
                db.save_version(app.current_note_id, title, content)

        if note["is_encrypted"] and app.current_note_id in app._decrypted_cache:
            app._decrypted_cache[app.current_note_id] = content
        else:
            db.update_note(app.current_note_id, title=title, content=content)

        sel = app.note_listbox.curselection()
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
            app.note_listbox.delete(idx)
            app.note_listbox.insert(idx, f"{prefix}{title}  [{date_str}]")
            app.note_listbox.selection_set(idx)

        app.status_var.set("Salvato")

    # --- Context Menu ---

    def show_context_menu(self, event):
        app = self.app
        # Select the note under cursor
        idx = app.note_listbox.nearest(event.y)
        if idx < 0 or idx >= len(app.notes):
            return
        app.note_listbox.selection_clear(0, tk.END)
        app.note_listbox.selection_set(idx)
        self.on_note_select()

        note = db.get_note(app.current_note_id)
        if not note:
            return

        menu = tk.Menu(app.root, tearoff=0)

        if app.show_trash:
            menu.add_command(label="Ripristina", command=lambda: self._restore_from_trash())
            menu.add_command(label="Elimina definitivamente", command=lambda: self._permanent_delete())
        else:
            pin_label = "Sgancia" if note["is_pinned"] else "Fissa in cima"
            fav_label = "Rimuovi dai preferiti" if note["is_favorite"] else "Aggiungi ai preferiti"
            menu.add_command(label=pin_label, command=self.toggle_pin)
            menu.add_command(label=fav_label, command=self.toggle_favorite)
            menu.add_separator()
            menu.add_command(label="Tag...", command=self.manage_tags)
            menu.add_command(label="Allegati...", command=self.manage_attachments)
            menu.add_command(label="Cronologia versioni...", command=self.show_versions)
            menu.add_separator()
            if note["is_encrypted"]:
                menu.add_command(label="Decripta...", command=self.decrypt_note)
            else:
                menu.add_command(label="Cripta...", command=self.encrypt_note)
            menu.add_separator()
            menu.add_command(label="Condividi (.mynote)...", command=lambda: app.export_ctl.export_mynote())
            menu.add_command(label="Esporta HTML...", command=lambda: app.export_ctl.export_html())
            menu.add_separator()
            menu.add_command(label="Sposta nel cestino", command=self.delete_note)

        menu.tk_popup(event.x_root, event.y_root)

    def _restore_from_trash(self):
        if self.app.current_note_id is None:
            return
        db.restore_note(self.app.current_note_id)
        self.app.current_note_id = None
        self.load_categories()
        self.load_notes()

    def _permanent_delete(self):
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if messagebox.askyesno("Conferma", f"Eliminare '{note['title']}' definitivamente?\nQuesta azione non puo' essere annullata."):
            db.permanent_delete_note(app.current_note_id)
            app.current_note_id = None
            self.load_categories()
            self.load_notes()

    # --- Checklist ---

    def insert_checklist(self):
        if self.app.current_note_id is None:
            messagebox.showinfo("Info", "Seleziona una nota prima.")
            return
        self.app.text_editor.insert(tk.INSERT, "\n[ ] Elemento da fare\n[ ] Altro elemento\n[x] Elemento completato\n")
        self._apply_checklist_formatting()

    def _apply_checklist_formatting(self):
        editor = self.app.text_editor
        editor.tag_remove("checkbox_done", "1.0", tk.END)
        editor.tag_remove("checkbox_open", "1.0", tk.END)

        content = editor.get("1.0", tk.END)
        for i, line in enumerate(content.split("\n"), 1):
            if line.strip().startswith("[x]"):
                editor.tag_add("checkbox_done", f"{i}.0", f"{i}.end")
            elif line.strip().startswith("[ ]"):
                editor.tag_add("checkbox_open", f"{i}.0", f"{i}.end")

    def on_text_click(self, event):
        editor = self.app.text_editor
        index = editor.index(f"@{event.x},{event.y}")
        line_num = int(index.split(".")[0])
        line = editor.get(f"{line_num}.0", f"{line_num}.end")
        stripped = line.lstrip()

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

    # --- Note Actions ---

    def new_note(self):
        app = self.app
        categories = db.get_all_categories()
        dlg = NoteDialog(app.root, categories)
        if dlg.result:
            note_id = db.add_note(dlg.result["title"], category_id=dlg.result["category_id"])
            app.show_trash = False
            self.load_categories()
            self.load_notes()
            for i, n in enumerate(app.notes):
                if n["id"] == note_id:
                    app.note_listbox.selection_clear(0, tk.END)
                    app.note_listbox.selection_set(i)
                    self.display_note(note_id)
                    break
            app.text_editor.focus_set()

    def delete_note(self):
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if app.show_trash:
            action = messagebox.askyesnocancel(
                "Cestino",
                f"'{note['title']}'\n\nSi = Elimina definitivamente\nNo = Ripristina\nAnnulla = Niente"
            )
            if action is True:
                db.permanent_delete_note(app.current_note_id)
            elif action is False:
                db.restore_note(app.current_note_id)
            else:
                return
        else:
            if messagebox.askyesno("Conferma", f"Spostare '{note['title']}' nel cestino?"):
                db.soft_delete_note(app.current_note_id)
            else:
                return
        app.current_note_id = None
        self.load_categories()
        self.load_notes()

    def toggle_pin(self):
        if self.app.current_note_id is None:
            return
        db.toggle_pin(self.app.current_note_id)
        self.load_notes()

    def toggle_favorite(self):
        if self.app.current_note_id is None:
            return
        db.toggle_favorite(self.app.current_note_id)
        self.load_notes()

    # --- Categories ---

    def new_category(self):
        dlg = CategoryDialog(self.app.root, title="Nuova Categoria")
        if dlg.result:
            db.add_category(dlg.result)
            self.load_categories()

    def rename_category(self):
        app = self.app
        if app.current_category_id is None:
            messagebox.showinfo("Info", "Seleziona una categoria dalla sidebar.")
            return
        cat = next((c for c in app.categories if c["id"] == app.current_category_id), None)
        if not cat:
            return
        dlg = CategoryDialog(app.root, title="Rinomina Categoria", initial_name=cat["name"])
        if dlg.result:
            db.rename_category(app.current_category_id, dlg.result)
            self.load_categories()

    def delete_category(self):
        app = self.app
        if app.current_category_id is None:
            messagebox.showinfo("Info", "Seleziona una categoria dalla sidebar.")
            return
        cat = next((c for c in app.categories if c["id"] == app.current_category_id), None)
        if not cat:
            return
        if messagebox.askyesno("Conferma", f"Eliminare '{cat['name']}'?\nLe note non verranno eliminate."):
            db.delete_category(app.current_category_id)
            app.current_category_id = None
            self.load_categories()
            self.load_notes()

    # --- Tags & Attachments ---

    def manage_tags(self):
        if self.app.current_note_id is None:
            return
        TagManagerDialog(self.app.root, self.app.current_note_id)
        self.display_note(self.app.current_note_id)
        self.load_categories()

    def manage_attachments(self):
        if self.app.current_note_id is None:
            return
        AttachmentDialog(self.app.root, self.app.current_note_id)
        self.display_note(self.app.current_note_id)

    # --- Version History ---

    def show_versions(self):
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if not note:
            return
        if note["is_encrypted"]:
            messagebox.showinfo("Info", "La cronologia versioni non e' disponibile per le note criptate.")
            return
        content = app.text_editor.get("1.0", tk.END).rstrip("\n")
        db.save_version(app.current_note_id, note["title"], content)
        dlg = VersionHistoryDialog(app.root, app.current_note_id)
        if dlg.result:
            self.display_note(app.current_note_id)

    # --- Encryption ---

    def encrypt_note(self):
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if note["is_encrypted"]:
            messagebox.showinfo("Info", "La nota e' gia' criptata.")
            return

        dlg = PasswordDialog(app.root, title="Cripta nota", confirm=True)
        if dlg.result:
            content = app.text_editor.get("1.0", tk.END).rstrip("\n")
            encrypted = crypto_utils.encrypt(content, dlg.result)
            db.set_note_encrypted(app.current_note_id, encrypted, True)
            # Remove all plaintext versions for security
            db.delete_note_versions(app.current_note_id)
            app._decrypted_cache.pop(app.current_note_id, None)
            self.display_note(app.current_note_id)
            app.status_var.set("Nota criptata")

    def decrypt_note(self):
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if not note["is_encrypted"]:
            messagebox.showinfo("Info", "La nota non e' criptata.")
            return

        dlg = PasswordDialog(app.root, title="Decripta nota")
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
                db.set_note_encrypted(app.current_note_id, decrypted, False)
                app._decrypted_cache.pop(app.current_note_id, None)
            elif action is False:
                app._decrypted_cache[app.current_note_id] = decrypted
            else:
                return
            self.display_note(app.current_note_id)
