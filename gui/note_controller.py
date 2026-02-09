"""Note CRUD, categories, tags, encryption, checklist, audio markers (PySide6)."""

import os
from PySide6.QtWidgets import (QMessageBox, QMenu, QListWidgetItem)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from datetime import datetime
import database as db
import crypto_utils
import platform_utils
import audio_utils
from gui.constants import (AUTO_SAVE_MS, VERSION_SAVE_EVERY,
                           FG_PRIMARY, FG_ON_ACCENT,
                           ACCENT, DANGER, WARNING, SELECT_BG, SELECT_FG)
from gui.formatting import apply_checklist_formatting, apply_audio_formatting
from dialogs import (CategoryDialog, NoteDialog, TagManagerDialog, AttachmentDialog,
                     VersionHistoryDialog, PasswordDialog)


class NoteController:
    def __init__(self, app):
        self.app = app
        self._displaying = False  # reentrancy guard
        self.app.text_editor.set_app(app)
        # Connect drag-and-drop signal from category list
        self.app.cat_listbox.notes_dropped.connect(self._on_notes_dropped)
        # Connect inline decrypt overlay
        self.app.decrypt_btn.clicked.connect(self._inline_decrypt)
        self.app.decrypt_entry.returnPressed.connect(self._inline_decrypt)

    # --- Data Loading ---

    def load_categories(self):
        app = self.app
        app.cat_listbox.clear()

        app.cat_listbox.addItem("  Tutte le note")
        app.cat_listbox.addItem("  Preferite")

        app.categories = db.get_all_categories()
        for cat in app.categories:
            app.cat_listbox.addItem(f"  {cat['name']}")

        trash_count = db.get_trash_count()
        app.cat_listbox.addItem(f"  Cestino ({trash_count})")

        last_idx = app.cat_listbox.count() - 1
        # Color the Preferite item
        item_fav = app.cat_listbox.item(1)
        if item_fav:
            item_fav.setForeground(QColor(WARNING))
        # Color the Cestino item
        item_trash = app.cat_listbox.item(last_idx)
        if item_trash:
            item_trash.setForeground(QColor(DANGER))

        app.cat_listbox.blockSignals(True)
        app.cat_listbox.setCurrentRow(0)
        app.cat_listbox.blockSignals(False)

        all_tags = db.get_all_tags()
        app.tag_combo.blockSignals(True)
        app.tag_combo.clear()
        app.tag_combo.addItem("(Tutti)")
        for t in all_tags:
            app.tag_combo.addItem(t["name"])
        app.tag_combo.setCurrentIndex(0)
        app.tag_combo.blockSignals(False)
        app.all_tags = all_tags

    def load_notes(self, preserve_selection=True):
        app = self.app
        prev_note_id = app.current_note_id if preserve_selection else None

        app.note_listbox.blockSignals(True)
        app.note_listbox.clear()
        search = app.search_entry.text().strip() or None

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
            item = QListWidgetItem(f"{prefix}{note['title']}  [{date_str}]")
            item.setData(Qt.UserRole, note["id"])
            app.note_listbox.addItem(item)

        header = "Cestino" if app.show_trash else ("Preferite" if app.show_favorites else "Note")
        app.list_header.setText(f"{header} ({len(app.notes)})")
        app.statusBar().showMessage(f"{len(app.notes)} nota/e")

        target_row = 0
        if app.notes:
            if prev_note_id is not None:
                for i, note in enumerate(app.notes):
                    if note["id"] == prev_note_id:
                        target_row = i
                        break
            app.note_listbox.setCurrentRow(target_row)
        app.note_listbox.blockSignals(False)

        if app.notes:
            self.display_note(app.notes[target_row]["id"])
        else:
            self._clear_editor()

    # --- Event Handlers ---

    def _flush_save(self):
        """Stop pending autosave timer and save immediately."""
        app = self.app
        if app._save_job:
            app._save_job.stop()
            app._save_job = None
        self.save_current()

    def on_category_select(self):
        app = self.app
        row = app.cat_listbox.currentRow()
        if row < 0:
            return
        app.show_trash = False
        app.show_favorites = False
        app.current_category_id = None

        if row == 0:
            pass
        elif row == 1:
            app.show_favorites = True
        elif row == app.cat_listbox.count() - 1:
            app.show_trash = True
        else:
            app.current_category_id = app.categories[row - 2]["id"]
        self._flush_save()
        self.load_notes()

    def on_note_select(self):
        if self._displaying:
            return
        items = self.app.note_listbox.selectedItems()
        if not items:
            return
        if len(items) == 1:
            note_id = items[0].data(Qt.UserRole)
            if note_id is not None:
                self.display_note(note_id)
        else:
            self.save_current()
            self._clear_editor()
            self.app.statusBar().showMessage(f"{len(items)} note selezionate")

    def focus_search(self):
        self.app.search_entry.setFocus()
        self.app.search_entry.selectAll()

    def clear_search(self):
        if self.app.search_entry.text():
            self.app.search_entry.clear()
        else:
            self.app.text_editor.setFocus()

    def on_search(self):
        self._flush_save()
        self.load_notes()

    def on_tag_filter(self):
        app = self.app
        idx = app.tag_combo.currentIndex()
        app.current_tag_id = None if idx <= 0 else app.all_tags[idx - 1]["id"]
        self._flush_save()
        self.load_notes()

    def on_note_double_click(self, item):
        note_id = item.data(Qt.UserRole)
        if note_id is not None:
            self.app.open_in_window(note_id)

    # --- Drag-and-Drop ---

    def _on_notes_dropped(self, indices, target_row):
        """Handle notes dropped onto category list."""
        app = self.app
        if target_row < 0:
            return
        last_idx = app.cat_listbox.count() - 1

        # Ignore drop on Preferite (1) and Cestino (last)
        if target_row == 1 or target_row == last_idx:
            return

        # Determine target category_id
        if target_row == 0:
            target_id = db._UNSET
        else:
            target_id = app.categories[target_row - 2]["id"]

        # Move all selected notes
        self.save_current()
        for idx in indices:
            if idx < len(app.notes):
                note_id = app.notes[idx]["id"]
                db.update_note(note_id, category_id=target_id)

        # Reload
        app.current_note_id = None
        self.load_categories()
        app.cat_listbox.setCurrentRow(target_row)
        self.on_category_select()

    # --- Editor ---

    def display_note(self, note_id):
        app = self.app
        if self._displaying:
            return
        if note_id in app._detached_windows:
            return
        self._displaying = True
        try:
            self._display_note_inner(note_id)
        finally:
            self._displaying = False

    def _display_note_inner(self, note_id):
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

        app.title_entry.blockSignals(True)
        app.title_entry.setText(note["title"])
        app.title_entry.blockSignals(False)

        app.text_editor.setReadOnly(False)
        app.text_editor.blockSignals(True)
        app.text_editor.clear()

        if note["is_encrypted"]:
            if note_id in app._decrypted_cache:
                app.editor_stack.setCurrentIndex(0)
                app.text_editor.setPlainText(app._decrypted_cache[note_id])
            else:
                app.editor_stack.setCurrentIndex(1)
                app.decrypt_entry.clear()
                app.decrypt_error_label.setText("")
                app.text_editor.setReadOnly(True)
        else:
            app.editor_stack.setCurrentIndex(0)
            app.text_editor.setPlainText(note["content"] or "")
            self._apply_checklist_formatting()
            self._apply_audio_formatting()

        app.text_editor.blockSignals(False)

        created = note["created_at"][:16].replace("T", " ")
        updated = note["updated_at"][:16].replace("T", " ")
        meta = f"Creata: {created}  |  Modificata: {updated}"
        if note["is_pinned"]:
            meta += "  |  Fissata"
        if note["is_favorite"]:
            meta += "  |  Preferita"
        if note["is_encrypted"]:
            meta += "  |  Criptata"
        app.meta_label.setText(meta)

        tags = db.get_note_tags(note_id)
        tag_str = "Tag: " + ", ".join(f"#{t['name']}" for t in tags) if tags else "Nessun tag"
        att_count = len(db.get_note_attachments(note_id))
        if att_count > 0:
            tag_str += f"  |  {att_count} allegato/i"
        app.tags_label.setText(tag_str)

        app.media_ctl.load_gallery(note_id)

    def _clear_editor(self):
        app = self.app
        app.current_note_id = None
        app.editor_stack.setCurrentIndex(0)
        app.title_entry.blockSignals(True)
        app.title_entry.clear()
        app.title_entry.blockSignals(False)
        app.text_editor.setReadOnly(False)
        app.text_editor.blockSignals(True)
        app.text_editor.clear()
        app.text_editor.blockSignals(False)
        app.meta_label.setText("")
        app.tags_label.setText("")
        app._image_refs.clear()
        # Clear gallery
        layout = app.gallery_inner_layout
        while layout.count() > 0:
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        layout.addStretch()

    def schedule_save(self):
        app = self.app
        if app._save_job:
            app._save_job.stop()
        timer = QTimer(app)
        timer.setSingleShot(True)
        timer.timeout.connect(self.save_current)
        timer.start(AUTO_SAVE_MS)
        app._save_job = timer

    def save_current(self):
        app = self.app
        app._save_job = None
        if app.current_note_id is None:
            return
        # Don't save if editor is read-only (encrypted placeholder)
        if app.text_editor.isReadOnly():
            return
        note = db.get_note(app.current_note_id)
        if not note or (note["is_encrypted"] and app.current_note_id not in app._decrypted_cache):
            return

        title = app.title_entry.text().strip()
        content = app.text_editor.toPlainText()
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

        # Update list item text (block signals to prevent cascade)
        app.note_listbox.blockSignals(True)
        items = app.note_listbox.findItems("*", Qt.MatchWildcard)
        for item in items:
            if item.data(Qt.UserRole) == app.current_note_id:
                date_str = datetime.now().isoformat()[:10]
                prefix = ""
                if note["is_pinned"]:
                    prefix += "[P] "
                if note["is_favorite"]:
                    prefix += "[*] "
                if note["is_encrypted"]:
                    prefix += "[E] "
                item.setText(f"{prefix}{title}  [{date_str}]")
                break
        app.note_listbox.blockSignals(False)

        app.statusBar().showMessage("Salvato")

    # --- Context Menu ---

    def show_category_context_menu(self, pos):
        app = self.app
        item = app.cat_listbox.itemAt(pos)
        if not item:
            return
        idx = app.cat_listbox.row(item)
        app.cat_listbox.setCurrentRow(idx)
        self.on_category_select()

        menu = QMenu(app)
        last_idx = app.cat_listbox.count() - 1
        is_user_category = 2 <= idx < last_idx

        if is_user_category:
            cat_id = app.categories[idx - 2]["id"]
            menu.addAction("Rinomina", self.rename_category)
            menu.addAction("Elimina", self.delete_category)
            menu.addAction("Svuota categoria", self.empty_category)
            # Submenu "Sposta note in"
            move_menu = menu.addMenu("Sposta note in")
            move_menu.addAction("Nessuna categoria",
                                lambda cid=cat_id: self._move_category_notes_to(cid, db._UNSET))
            for cat in app.categories:
                if cat["id"] != cat_id:
                    move_menu.addAction(
                        cat["name"],
                        lambda from_id=cat_id, to_id=cat["id"]: self._move_category_notes_to(from_id, to_id))
            menu.addSeparator()

        menu.addAction("Nuova Categoria", self.new_category)
        menu.popup(app.cat_listbox.mapToGlobal(pos))

    def show_context_menu(self, pos):
        app = self.app
        item = app.note_listbox.itemAt(pos)
        if not item:
            return
        idx = app.note_listbox.row(item)
        if idx < 0 or idx >= len(app.notes):
            return

        selected_items = app.note_listbox.selectedItems()
        selected_rows = [app.note_listbox.row(si) for si in selected_items]

        if len(selected_rows) > 1 and idx in selected_rows:
            # Multi-selection context menu
            self.save_current()
            menu = QMenu(app)
            self._build_multi_context_menu(menu, selected_rows)
            menu.popup(app.note_listbox.mapToGlobal(pos))
            return

        # Single note context menu
        app.note_listbox.setCurrentRow(idx)
        self.on_note_select()

        note = db.get_note(app.current_note_id)
        if not note:
            return

        menu = QMenu(app)

        if app.show_trash:
            menu.addAction("Ripristina", self._restore_from_trash)
            menu.addAction("Elimina definitivamente", self._permanent_delete)
        else:
            menu.addAction("Apri in finestra",
                           lambda nid=app.current_note_id: app.open_in_window(nid))
            menu.addSeparator()
            pin_label = "Sgancia" if note["is_pinned"] else "Fissa in cima"
            fav_label = "Rimuovi dai preferiti" if note["is_favorite"] else "Aggiungi ai preferiti"
            menu.addAction(pin_label, self.toggle_pin)
            menu.addAction(fav_label, self.toggle_favorite)
            menu.addSeparator()
            menu.addAction("Tag...", self.manage_tags)
            menu.addAction("Allegati...", self.manage_attachments)
            menu.addAction("Cronologia versioni...", self.show_versions)
            menu.addSeparator()
            menu.addAction("Inserisci checklist", self.insert_checklist)
            menu.addSeparator()
            menu.addAction("Screenshot intero", lambda: app.media_ctl.take_screenshot())
            menu.addAction("Screenshot regione", lambda: app.media_ctl.take_screenshot_region())
            menu.addAction("Inserisci immagine...", lambda: app.media_ctl.insert_image())
            menu.addSeparator()
            menu.addAction("Registra audio...", lambda: app.media_ctl.record_audio())
            menu.addAction("Importa audio...", lambda: app.media_ctl.import_audio())
            menu.addSeparator()
            if note["is_encrypted"]:
                menu.addAction("Decripta...", self.decrypt_note)
            else:
                menu.addAction("Cripta...", self.encrypt_note)
            menu.addSeparator()
            menu.addAction("Condividi (.mynote)...", lambda: app.export_ctl.export_mynote())
            menu.addAction("Esporta HTML...", lambda: app.export_ctl.export_html())
            menu.addAction("Esporta PDF...", lambda: app.export_ctl.export_pdf())
            menu.addSeparator()
            menu.addAction("Sposta nel cestino", self.delete_note)

        menu.popup(app.note_listbox.mapToGlobal(pos))

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
        if QMessageBox.question(
            app, "Conferma",
            f"Eliminare '{note['title']}' definitivamente?\nQuesta azione non puo' essere annullata."
        ) == QMessageBox.Yes:
            db.permanent_delete_note(app.current_note_id)
            app.current_note_id = None
            self.load_categories()
            self.load_notes()

    # --- Multi-select actions ---

    def _build_multi_context_menu(self, menu, sel):
        n = len(sel)
        app = self.app
        if app.show_trash:
            menu.addAction(f"Ripristina {n} note",
                           lambda: self._restore_multiple(sel))
            menu.addAction(f"Elimina definitivamente {n} note",
                           lambda: self._permanent_delete_multiple(sel))
        else:
            menu.addAction(f"Fissa {n} note",
                           lambda: self._pin_multiple(sel, True))
            menu.addAction(f"Sgancia {n} note",
                           lambda: self._pin_multiple(sel, False))
            menu.addSeparator()
            menu.addAction(f"Aggiungi {n} note ai preferiti",
                           lambda: self._favorite_multiple(sel, True))
            menu.addAction(f"Rimuovi {n} note dai preferiti",
                           lambda: self._favorite_multiple(sel, False))
            menu.addSeparator()
            move_menu = menu.addMenu("Sposta in")
            move_menu.addAction("Nessuna categoria",
                                lambda: self._move_multiple_to_category(sel, db._UNSET))
            for cat in app.categories:
                move_menu.addAction(cat["name"],
                                    lambda cid=cat["id"]: self._move_multiple_to_category(sel, cid))
            menu.addSeparator()
            menu.addAction(f"Sposta {n} note nel cestino",
                           lambda: self._soft_delete_multiple(sel))

    def _soft_delete_multiple(self, sel):
        app = self.app
        n = len(sel)
        if QMessageBox.question(app, "Conferma",
                                f"Spostare {n} note nel cestino?") != QMessageBox.Yes:
            return
        self.save_current()
        ids = [app.notes[i]["id"] for i in sel if i < len(app.notes)]
        db.soft_delete_notes(ids)
        app.current_note_id = None
        self.load_categories()
        self.load_notes()

    def _permanent_delete_multiple(self, sel):
        app = self.app
        n = len(sel)
        if QMessageBox.question(
            app, "Conferma",
            f"Eliminare definitivamente {n} note?\nQuesta azione non puo' essere annullata."
        ) != QMessageBox.Yes:
            return
        self.save_current()
        ids = [app.notes[i]["id"] for i in sel if i < len(app.notes)]
        db.permanent_delete_notes(ids)
        app.current_note_id = None
        self.load_categories()
        self.load_notes()

    def _restore_multiple(self, sel):
        app = self.app
        ids = [app.notes[i]["id"] for i in sel if i < len(app.notes)]
        db.restore_notes(ids)
        app.current_note_id = None
        self.load_categories()
        self.load_notes()

    def _pin_multiple(self, sel, value):
        ids = [self.app.notes[i]["id"] for i in sel if i < len(self.app.notes)]
        db.set_pinned_notes(ids, value)
        self.load_notes()

    def _favorite_multiple(self, sel, value):
        ids = [self.app.notes[i]["id"] for i in sel if i < len(self.app.notes)]
        db.set_favorite_notes(ids, value)
        self.load_notes()

    def _move_multiple_to_category(self, sel, cat_id):
        self.save_current()
        ids = [self.app.notes[i]["id"] for i in sel if i < len(self.app.notes)]
        db.move_notes_to_category(ids, cat_id)
        self.app.current_note_id = None
        self.load_categories()
        self.load_notes()

    def empty_category(self):
        app = self.app
        if app.current_category_id is None:
            QMessageBox.information(app, "Info", "Seleziona una categoria dalla sidebar.")
            return
        cat = next((c for c in app.categories if c["id"] == app.current_category_id), None)
        if not cat:
            return
        note_ids = db.get_note_ids_by_category(app.current_category_id)
        if not note_ids:
            QMessageBox.information(app, "Info", f"La categoria '{cat['name']}' e' gia' vuota.")
            return
        if QMessageBox.question(
            app, "Svuota Categoria",
            f"Spostare {len(note_ids)} nota/e di '{cat['name']}' nel cestino?"
        ) != QMessageBox.Yes:
            return
        self.save_current()
        db.soft_delete_notes(note_ids)
        app.current_note_id = None
        self.load_categories()
        self.load_notes()

    def _move_category_notes_to(self, from_cat_id, to_cat_id):
        note_ids = db.get_note_ids_by_category(from_cat_id)
        if not note_ids:
            QMessageBox.information(self.app, "Info", "La categoria e' vuota.")
            return
        self.save_current()
        db.move_notes_to_category(note_ids, to_cat_id)
        self.app.current_note_id = None
        self.load_categories()
        self.load_notes()

    # --- Checklist ---

    def insert_checklist(self):
        if self.app.current_note_id is None:
            QMessageBox.information(self.app, "Info", "Seleziona una nota prima.")
            return
        cursor = self.app.text_editor.textCursor()
        cursor.insertText("\n[ ] Elemento da fare\n[ ] Altro elemento\n[x] Elemento completato\n")
        self._apply_checklist_formatting()

    def _apply_checklist_formatting(self):
        apply_checklist_formatting(self.app.text_editor)

    def _apply_audio_formatting(self):
        apply_audio_formatting(self.app.text_editor)

    def insert_audio_marker(self, att_filename, description):
        """Inserisce un marker audio alla posizione del cursore."""
        if self.app.current_note_id is None:
            return
        desc = description or "audio"
        marker = f"\n[♪:{att_filename} {desc}]\n"
        cursor = self.app.text_editor.textCursor()
        cursor.insertText(marker)
        self._apply_audio_formatting()
        self._apply_checklist_formatting()
        self.schedule_save()

    # --- Note Actions ---

    def new_note(self):
        app = self.app
        categories = db.get_all_categories()
        dlg = NoteDialog(app, categories)
        if dlg.result:
            note_id = db.add_note(dlg.result["title"], category_id=dlg.result["category_id"])
            app.show_trash = False
            self.load_categories()
            self.load_notes()
            for i in range(app.note_listbox.count()):
                item = app.note_listbox.item(i)
                if item.data(Qt.UserRole) == note_id:
                    app.note_listbox.setCurrentRow(i)
                    self.display_note(note_id)
                    break
            app.text_editor.setFocus()

    def delete_note(self):
        app = self.app
        selected_items = app.note_listbox.selectedItems()
        if not selected_items:
            return

        selected_rows = [app.note_listbox.row(si) for si in selected_items]

        # Multi-selection
        if len(selected_rows) > 1:
            if app.show_trash:
                self._permanent_delete_multiple(selected_rows)
            else:
                self._soft_delete_multiple(selected_rows)
            return

        # Single note
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if app.show_trash:
            btn = QMessageBox.question(
                app, "Cestino",
                f"'{note['title']}'\n\nEliminare definitivamente o ripristinare?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Cancel
            )
            if btn == QMessageBox.Yes:
                db.permanent_delete_note(app.current_note_id)
            elif btn == QMessageBox.No:
                db.restore_note(app.current_note_id)
            else:
                return
        else:
            if QMessageBox.question(
                app, "Conferma",
                f"Spostare '{note['title']}' nel cestino?"
            ) != QMessageBox.Yes:
                return
            db.soft_delete_note(app.current_note_id)
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
        dlg = CategoryDialog(self.app, title="Nuova Categoria")
        if dlg.result:
            db.add_category(dlg.result)
            self.load_categories()

    def rename_category(self):
        app = self.app
        if app.current_category_id is None:
            QMessageBox.information(app, "Info", "Seleziona una categoria dalla sidebar.")
            return
        cat = next((c for c in app.categories if c["id"] == app.current_category_id), None)
        if not cat:
            return
        dlg = CategoryDialog(app, title="Rinomina Categoria", initial_name=cat["name"])
        if dlg.result:
            db.rename_category(app.current_category_id, dlg.result)
            self.load_categories()

    def delete_category(self):
        app = self.app
        if app.current_category_id is None:
            QMessageBox.information(app, "Info", "Seleziona una categoria dalla sidebar.")
            return
        cat = next((c for c in app.categories if c["id"] == app.current_category_id), None)
        if not cat:
            return

        note_ids = db.get_note_ids_by_category(app.current_category_id)
        if note_ids:
            btn = QMessageBox.question(
                app, "Elimina Categoria",
                f"La categoria '{cat['name']}' contiene {len(note_ids)} nota/e.\n\n"
                f"Si = Elimina categoria e sposta note nel cestino\n"
                f"No = Elimina solo la categoria (le note restano)\n"
                f"Annulla = Non fare nulla",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Cancel
            )
            if btn == QMessageBox.Yes:
                db.delete_category_with_notes(app.current_category_id)
            elif btn == QMessageBox.No:
                db.delete_category(app.current_category_id)
            else:
                return
        else:
            if QMessageBox.question(
                app, "Conferma",
                f"Eliminare la categoria '{cat['name']}'?"
            ) != QMessageBox.Yes:
                return
            db.delete_category(app.current_category_id)

        app.current_category_id = None
        self.load_categories()
        self.load_notes()

    # --- Tags & Attachments ---

    def manage_tags(self):
        if self.app.current_note_id is None:
            return
        TagManagerDialog(self.app, self.app.current_note_id)
        self.display_note(self.app.current_note_id)
        self.load_categories()

    def manage_attachments(self):
        if self.app.current_note_id is None:
            return
        AttachmentDialog(self.app, self.app.current_note_id)
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
            QMessageBox.information(app, "Info",
                                    "La cronologia versioni non e' disponibile per le note criptate.")
            return
        content = app.text_editor.toPlainText()
        db.save_version(app.current_note_id, note["title"], content)
        dlg = VersionHistoryDialog(app, app.current_note_id)
        if dlg.result:
            self.display_note(app.current_note_id)

    # --- Inline Decrypt ---

    def _inline_decrypt(self):
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if not note or not note["is_encrypted"]:
            return
        password = app.decrypt_entry.text()
        if not password:
            return
        decrypted = crypto_utils.decrypt(note["content"], password)
        if decrypted is None:
            app.decrypt_error_label.setText("Password errata")
            app.decrypt_entry.selectAll()
            app.decrypt_entry.setFocus()
            return
        app._decrypted_cache[app.current_note_id] = decrypted
        app.decrypt_entry.clear()
        app.decrypt_error_label.setText("")
        self.display_note(app.current_note_id)

    # --- Encryption ---

    def encrypt_note(self):
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if note["is_encrypted"]:
            QMessageBox.information(app, "Info", "La nota e' gia' criptata.")
            return

        dlg = PasswordDialog(app, title="Cripta nota", confirm=True)
        if dlg.result:
            content = app.text_editor.toPlainText()
            encrypted = crypto_utils.encrypt(content, dlg.result)
            db.set_note_encrypted(app.current_note_id, encrypted, True)
            db.delete_note_versions(app.current_note_id)
            app._decrypted_cache.pop(app.current_note_id, None)
            self.display_note(app.current_note_id)
            app.statusBar().showMessage("Nota criptata")

    def decrypt_note(self):
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if not note["is_encrypted"]:
            QMessageBox.information(app, "Info", "La nota non e' criptata.")
            return

        dlg = PasswordDialog(app, title="Decripta nota")
        if dlg.result:
            decrypted = crypto_utils.decrypt(note["content"], dlg.result)
            if decrypted is None:
                QMessageBox.critical(app, "Errore", "Password errata.")
                return

            btn = QMessageBox.question(
                app, "Decripta",
                "Nota decriptata!\n\nSi = Rimuovi crittografia permanentemente\n"
                "No = Visualizza solo (resta criptata)\nAnnulla = Chiudi",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Cancel
            )
            if btn == QMessageBox.Yes:
                db.set_note_encrypted(app.current_note_id, decrypted, False)
                app._decrypted_cache.pop(app.current_note_id, None)
            elif btn == QMessageBox.No:
                app._decrypted_cache[app.current_note_id] = decrypted
            else:
                return
            self.display_note(app.current_note_id)
