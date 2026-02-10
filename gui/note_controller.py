"""Note CRUD, categories, tags, encryption, checklist, audio markers (PySide6)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QListWidgetItem, QMenu, QMessageBox, QTreeWidgetItem

import database as db

if TYPE_CHECKING:
    from gui import MyNotesApp
import crypto_utils
from dialogs import (
    AttachmentDialog,
    BulkTagDialog,
    CategoryDialog,
    NoteDialog,
    PasswordDialog,
    TagManagerDialog,
    VersionHistoryDialog,
)
from gui.constants import (
    AUTO_SAVE_MS,
    BG_DARK,
    DANGER,
    FG_PRIMARY,
    FONT_BASE,
    UI_FONT,
    VERSION_SAVE_EVERY,
    WARNING,
)
from gui.formatting import apply_audio_formatting, apply_checklist_formatting


class NoteController:
    def __init__(self, app: MyNotesApp) -> None:
        self.app = app
        self.app.text_editor.set_app(app)
        # Connect inline decrypt overlay
        self.app.decrypt_btn.clicked.connect(self._inline_decrypt)
        self.app.decrypt_entry.returnPressed.connect(self._inline_decrypt)

    # --- Data Loading ---

    def load_categories(self) -> None:
        app = self.app
        tree = app.cat_tree
        tree.clear()
        app._cat_items.clear()

        # Special items (top-level)
        item_all = QTreeWidgetItem(tree, ["Tutte le note"])
        item_all.setData(0, Qt.ItemDataRole.UserRole, "__all__")

        item_fav = QTreeWidgetItem(tree, ["Preferite"])
        item_fav.setData(0, Qt.ItemDataRole.UserRole, "__favorites__")
        item_fav.setForeground(0, QColor(WARNING))

        # Build category tree
        app.categories = db.get_all_categories()
        # Multi-pass: first root categories, then children iteratively
        remaining = list(app.categories)
        for _pass in range(20):
            still_remaining = []
            for cat in remaining:
                parent_id = cat["parent_id"]
                if parent_id is None:
                    item = QTreeWidgetItem(tree, [cat["name"]])
                    item.setData(0, Qt.ItemDataRole.UserRole, cat["id"])
                    app._cat_items[cat["id"]] = item
                elif parent_id in app._cat_items:
                    parent_item = app._cat_items[parent_id]
                    item = QTreeWidgetItem(parent_item, [cat["name"]])
                    item.setData(0, Qt.ItemDataRole.UserRole, cat["id"])
                    app._cat_items[cat["id"]] = item
                else:
                    still_remaining.append(cat)
            remaining = still_remaining
            if not remaining:
                break

        # Cestino (always last)
        trash_count = db.get_trash_count()
        item_trash = QTreeWidgetItem(tree, [f"Cestino ({trash_count})"])
        item_trash.setData(0, Qt.ItemDataRole.UserRole, "__trash__")
        item_trash.setForeground(0, QColor(DANGER))

        tree.expandAll()
        tree.setCurrentItem(item_all)

        # Tags combo
        all_tags = db.get_all_tags()
        app.tag_combo.blockSignals(True)
        app.tag_combo.clear()
        app.tag_combo.addItem("(Tutti)")
        for t in all_tags:
            app.tag_combo.addItem(t["name"])
        app.tag_combo.setCurrentIndex(0)
        app.tag_combo.blockSignals(False)
        app.all_tags = all_tags

    def load_notes(self, preserve_selection: bool = True) -> None:
        app = self.app
        prev_note_id = app.current_note_id if preserve_selection else None

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
            prefix = ""
            if note["is_pinned"]:
                prefix += "[P] "
            if note["is_favorite"]:
                prefix += "[*] "
            if note["is_encrypted"]:
                prefix += "[E] "
            item = QListWidgetItem(f"{prefix}{note['title']}")
            item.setData(Qt.ItemDataRole.UserRole, note["id"])
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

        if app.notes:
            self.display_note(app.notes[target_row]["id"])
        else:
            self._clear_editor()

    # --- Event Handlers ---

    def _flush_save(self) -> None:
        """Stop pending autosave timer and save immediately."""
        app = self.app
        if app._save_job:
            app._save_job.stop()
            app._save_job = None
        self.save_current()

    def on_category_select(self) -> None:
        app = self.app
        item = app.cat_tree.currentItem()
        if not item:
            return
        role = item.data(0, Qt.ItemDataRole.UserRole)
        app.show_trash = False
        app.show_favorites = False
        app.current_category_id = None

        if role == "__all__":
            pass
        elif role == "__favorites__":
            app.show_favorites = True
        elif role == "__trash__":
            app.show_trash = True
        elif isinstance(role, int):
            app.current_category_id = role
        self._flush_save()
        self.load_notes()

    def on_note_click(self, item: QListWidgetItem | None) -> None:
        """Handle user click on a note list item."""
        if not item:
            return
        items = self.app.note_listbox.selectedItems()
        if len(items) > 1:
            self.save_current()
            self._clear_editor()
            self.app.statusBar().showMessage(f"{len(items)} note selezionate")
            return
        note_id = item.data(Qt.ItemDataRole.UserRole)
        if note_id is not None:
            self.display_note(note_id)

    def on_note_select(self) -> None:
        """Used by show_context_menu() for programmatic single-note selection."""
        items = self.app.note_listbox.selectedItems()
        if not items:
            return
        if len(items) == 1:
            note_id = items[0].data(Qt.ItemDataRole.UserRole)
            if note_id is not None:
                self.display_note(note_id)

    def focus_search(self) -> None:
        self.app.search_entry.setFocus()
        self.app.search_entry.selectAll()

    def clear_search(self) -> None:
        if self.app.search_entry.text():
            self.app.search_entry.clear()
        else:
            self.app.text_editor.setFocus()

    def on_search(self) -> None:
        self._flush_save()
        self.load_notes()

    def on_tag_filter(self) -> None:
        app = self.app
        idx = app.tag_combo.currentIndex()
        app.current_tag_id = None if idx <= 0 else app.all_tags[idx - 1]["id"]
        self._flush_save()
        self.load_notes()

    def on_note_double_click(self, item: QListWidgetItem) -> None:
        note_id = item.data(Qt.ItemDataRole.UserRole)
        if note_id is not None:
            self.app.open_in_window(note_id)

    # --- Editor ---

    def display_note(self, note_id: int) -> None:
        app = self.app
        if note_id in app._detached_windows:
            return
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

        if app.editor_tabs.currentIndex() == 1:
            self.update_preview()

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

    def _clear_editor(self) -> None:
        app = self.app
        app.current_note_id = None
        app.editor_stack.setCurrentIndex(0)
        app.editor_tabs.setCurrentIndex(0)
        app.title_entry.blockSignals(True)
        app.title_entry.clear()
        app.title_entry.blockSignals(False)
        app.text_editor.setReadOnly(False)
        app.text_editor.blockSignals(True)
        app.text_editor.clear()
        app.text_editor.blockSignals(False)
        app.preview_browser.clear()
        app.meta_label.setText("")
        app.tags_label.setText("")
        app._image_refs.clear()
        # Clear gallery
        layout = app.gallery_inner_layout
        while layout.count() > 0:
            child = layout.takeAt(0)
            if child is not None and child.widget():
                child.widget().deleteLater()  # type: ignore[union-attr]
        layout.addStretch()

    def schedule_save(self) -> None:
        app = self.app
        if app._save_job:
            app._save_job.stop()
        timer = QTimer(app)
        timer.setSingleShot(True)
        timer.timeout.connect(self.save_current)
        timer.start(AUTO_SAVE_MS)
        app._save_job = timer

    def save_current(self) -> None:
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

        # Update list item text (safe: no currentRowChanged connected)
        items = app.note_listbox.findItems("*", Qt.MatchFlag.MatchWildcard)
        for item in items:
            if item.data(Qt.ItemDataRole.UserRole) == app.current_note_id:
                prefix = ""
                if note["is_pinned"]:
                    prefix += "[P] "
                if note["is_favorite"]:
                    prefix += "[*] "
                if note["is_encrypted"]:
                    prefix += "[E] "
                item.setText(f"{prefix}{title}")
                break

        app.statusBar().showMessage("Salvato")

    # --- Context Menu ---

    def show_category_context_menu(self, pos: QPoint) -> None:
        app = self.app
        item = app.cat_tree.itemAt(pos)
        if not item:
            return
        app.cat_tree.setCurrentItem(item)
        self.on_category_select()

        role = item.data(0, Qt.ItemDataRole.UserRole)
        menu = QMenu(app)
        is_user_category = isinstance(role, int)

        if is_user_category:
            cat_id = role
            menu.addAction("Nuova Sottocategoria", lambda: self.new_subcategory(cat_id))
            menu.addSeparator()
            menu.addAction("Rinomina", self.rename_category)
            # Submenu "Sposta in"
            descendants = db.get_descendant_category_ids(cat_id)
            excluded = {cat_id} | set(descendants)
            move_cat_menu = menu.addMenu("Sposta in")
            move_cat_menu.addAction("(Radice)", lambda cid=cat_id: self._reparent_category(cid, None))
            for cat in app.categories:
                if cat["id"] not in excluded:
                    path = db.get_category_path(cat["id"])
                    display = " > ".join(r["name"] for r in path)
                    move_cat_menu.addAction(
                        display,
                        lambda cid=cat_id, pid=cat["id"]: self._reparent_category(cid, pid),
                    )
            menu.addAction("Elimina", self.delete_category)
            menu.addSeparator()

        menu.addAction("Nuova Categoria", self.new_category)
        menu.popup(app.cat_tree.mapToGlobal(pos))

    def show_context_menu(self, pos: QPoint) -> None:
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

        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if not note:
            return

        menu = QMenu(app)

        if app.show_trash:
            menu.addAction("Ripristina", self._restore_from_trash)
            menu.addAction("Elimina definitivamente", self._permanent_delete)
        else:
            menu.addAction("Apri in finestra", lambda nid=app.current_note_id: app.open_in_window(nid))
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
            # Submenu "Sposta in" per singola nota
            move_menu = menu.addMenu("Sposta in")
            note_id = app.current_note_id
            move_menu.addAction(
                "Nessuna categoria",
                lambda nid=note_id: self._move_single_note(nid, db._UNSET),
            )
            for cat in app.categories:
                path = db.get_category_path(cat["id"])
                display = " > ".join(r["name"] for r in path)
                move_menu.addAction(
                    display,
                    lambda nid=note_id, cid=cat["id"]: self._move_single_note(nid, cid),
                )
            menu.addAction("Sposta nel cestino", self.delete_note)

        menu.popup(app.note_listbox.mapToGlobal(pos))

    def _restore_from_trash(self) -> None:
        if self.app.current_note_id is None:
            return
        db.restore_note(self.app.current_note_id)
        self.app.current_note_id = None
        self.load_categories()
        self.load_notes()

    def _permanent_delete(self) -> None:
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if note is None:
            return
        if (
            QMessageBox.question(
                app,
                "Conferma",
                f"Eliminare '{note['title']}' definitivamente?\nQuesta azione non puo' essere annullata.",
            )
            == QMessageBox.StandardButton.Yes
        ):
            db.permanent_delete_note(app.current_note_id)
            app.current_note_id = None
            self.load_categories()
            self.load_notes()

    # --- Multi-select actions ---

    def _build_multi_context_menu(self, menu: QMenu, sel: list[int]) -> None:
        n = len(sel)
        app = self.app
        if app.show_trash:
            menu.addAction(f"Ripristina {n} note", lambda: self._restore_multiple(sel))
            menu.addAction(f"Elimina definitivamente {n} note", lambda: self._permanent_delete_multiple(sel))
        else:
            menu.addAction(f"Fissa {n} note", lambda: self._pin_multiple(sel, True))
            menu.addAction(f"Sgancia {n} note", lambda: self._pin_multiple(sel, False))
            menu.addSeparator()
            menu.addAction(f"Aggiungi {n} note ai preferiti", lambda: self._favorite_multiple(sel, True))
            menu.addAction(f"Rimuovi {n} note dai preferiti", lambda: self._favorite_multiple(sel, False))
            menu.addSeparator()
            menu.addAction(f"Tag per {n} note...", lambda: self._tag_multiple(sel))
            menu.addSeparator()
            move_menu = menu.addMenu("Sposta in")
            move_menu.addAction("Nessuna categoria", lambda: self._move_multiple_to_category(sel, db._UNSET))
            for cat in app.categories:
                path = db.get_category_path(cat["id"])
                display = " > ".join(r["name"] for r in path)
                move_menu.addAction(display, lambda cid=cat["id"]: self._move_multiple_to_category(sel, cid))
            menu.addSeparator()
            menu.addAction(f"Sposta {n} note nel cestino", lambda: self._soft_delete_multiple(sel))

    def _soft_delete_multiple(self, sel: list[int]) -> None:
        app = self.app
        n = len(sel)
        if QMessageBox.question(app, "Conferma", f"Spostare {n} note nel cestino?") != QMessageBox.StandardButton.Yes:
            return
        self.save_current()
        ids = [app.notes[i]["id"] for i in sel if i < len(app.notes)]
        db.soft_delete_notes(ids)
        app.current_note_id = None
        self.load_categories()
        self.load_notes()

    def _permanent_delete_multiple(self, sel: list[int]) -> None:
        app = self.app
        n = len(sel)
        if (
            QMessageBox.question(
                app, "Conferma", f"Eliminare definitivamente {n} note?\nQuesta azione non puo' essere annullata."
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.save_current()
        ids = [app.notes[i]["id"] for i in sel if i < len(app.notes)]
        db.permanent_delete_notes(ids)
        app.current_note_id = None
        self.load_categories()
        self.load_notes()

    def _restore_multiple(self, sel: list[int]) -> None:
        app = self.app
        ids = [app.notes[i]["id"] for i in sel if i < len(app.notes)]
        db.restore_notes(ids)
        app.current_note_id = None
        self.load_categories()
        self.load_notes()

    def _pin_multiple(self, sel: list[int], value: bool) -> None:
        ids = [self.app.notes[i]["id"] for i in sel if i < len(self.app.notes)]
        db.set_pinned_notes(ids, value)
        self.load_notes()

    def _favorite_multiple(self, sel: list[int], value: bool) -> None:
        ids = [self.app.notes[i]["id"] for i in sel if i < len(self.app.notes)]
        db.set_favorite_notes(ids, value)
        self.load_notes()

    def _tag_multiple(self, sel: list[int]) -> None:
        ids = [self.app.notes[i]["id"] for i in sel if i < len(self.app.notes)]
        if not ids:
            return
        dlg = BulkTagDialog(self.app, ids)
        if dlg.result:
            self.load_categories()
            self.load_notes()

    def _move_single_note(self, note_id: int, cat_id: int | db._Sentinel) -> None:
        self.save_current()
        db.update_note(note_id, category_id=cat_id)
        self.load_categories()
        self.load_notes()

    def _move_multiple_to_category(self, sel: list[int], cat_id: int | db._Sentinel) -> None:
        self.save_current()
        ids = [self.app.notes[i]["id"] for i in sel if i < len(self.app.notes)]
        db.move_notes_to_category(ids, cat_id)
        self.app.current_note_id = None
        self.load_categories()
        self.load_notes()

    # --- Checklist ---

    def insert_checklist(self) -> None:
        if self.app.current_note_id is None:
            QMessageBox.information(self.app, "Info", "Seleziona una nota prima.")
            return
        cursor = self.app.text_editor.textCursor()
        cursor.insertText("\n[ ] Elemento da fare\n[ ] Altro elemento\n[x] Elemento completato\n")
        self._apply_checklist_formatting()

    def _apply_checklist_formatting(self) -> None:
        apply_checklist_formatting(self.app.text_editor)

    def _apply_audio_formatting(self) -> None:
        apply_audio_formatting(self.app.text_editor)

    def update_preview(self) -> None:
        """Render markdown content to HTML in the preview tab."""
        import markdown

        content = self.app.text_editor.toPlainText()
        html = markdown.markdown(content, extensions=["fenced_code", "tables", "nl2br"])
        styled = (
            f"<div style=\"font-family: '{UI_FONT}', sans-serif; "
            f"color: {FG_PRIMARY}; background-color: {BG_DARK}; "
            f'font-size: {FONT_BASE + 1}pt; line-height: 1.6;">'
            f"{html}</div>"
        )
        self.app.preview_browser.setHtml(styled)

    def toggle_preview(self) -> None:
        """Toggle between edit and preview tabs."""
        tabs = self.app.editor_tabs
        tabs.setCurrentIndex(1 if tabs.currentIndex() == 0 else 0)

    def insert_audio_marker(self, att_filename: str, description: str) -> None:
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

    def new_note(self) -> None:
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
                if item.data(Qt.ItemDataRole.UserRole) == note_id:
                    app.note_listbox.setCurrentRow(i)
                    self.display_note(note_id)
                    break
            app.text_editor.setFocus()

    def delete_note(self) -> None:
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
        if note is None:
            return
        if app.show_trash:
            btn = QMessageBox.question(
                app,
                "Cestino",
                f"'{note['title']}'\n\nEliminare definitivamente o ripristinare?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if btn == QMessageBox.StandardButton.Yes:
                db.permanent_delete_note(app.current_note_id)
            elif btn == QMessageBox.StandardButton.No:
                db.restore_note(app.current_note_id)
            else:
                return
        else:
            reply = QMessageBox.question(app, "Conferma", f"Spostare '{note['title']}' nel cestino?")
            if reply != QMessageBox.StandardButton.Yes:
                return
            db.soft_delete_note(app.current_note_id)
        app.current_note_id = None
        self.load_categories()
        self.load_notes()

    def toggle_pin(self) -> None:
        if self.app.current_note_id is None:
            return
        db.toggle_pin(self.app.current_note_id)
        self.load_notes()

    def toggle_favorite(self) -> None:
        if self.app.current_note_id is None:
            return
        db.toggle_favorite(self.app.current_note_id)
        self.load_notes()

    # --- Categories ---

    def new_category(self) -> None:
        dlg = CategoryDialog(self.app, title="Nuova Categoria")
        if dlg.result:
            db.add_category(dlg.result)
            self.load_categories()

    def new_subcategory(self, parent_id: int) -> None:
        dlg = CategoryDialog(self.app, title="Nuova Sottocategoria")
        if dlg.result:
            db.add_category(dlg.result, parent_id=parent_id)
            self.load_categories()

    def _reparent_category(self, cat_id: int, new_parent_id: int | None) -> None:
        if not db.move_category(cat_id, new_parent_id):
            QMessageBox.warning(
                self.app, "Errore", "Impossibile spostare: la destinazione e' un discendente della categoria."
            )
            return
        self.load_categories()
        if cat_id in self.app._cat_items:
            self.app.cat_tree.setCurrentItem(self.app._cat_items[cat_id])
        self.on_category_select()

    def rename_category(self) -> None:
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

    def delete_category(self) -> None:
        app = self.app
        if app.current_category_id is None:
            QMessageBox.information(app, "Info", "Seleziona una categoria dalla sidebar.")
            return
        cat = next((c for c in app.categories if c["id"] == app.current_category_id), None)
        if not cat:
            return

        descendants = db.get_descendant_category_ids(app.current_category_id)
        own_notes = db.get_note_ids_by_category(app.current_category_id)
        has_children = len(descendants) > 0

        if own_notes or has_children:
            msg = f"Eliminare '{cat['name']}'?\n\n"
            if own_notes:
                msg += f"Le {len(own_notes)} note verranno spostate nel cestino.\n"
            if has_children:
                msg += "Le sottocategorie verranno mantenute al livello superiore.\n"
        else:
            msg = f"Eliminare la categoria '{cat['name']}'?"

        reply = QMessageBox.question(app, "Elimina Categoria", msg)
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.save_current()
        if has_children:
            db.promote_children(app.current_category_id)
        if own_notes:
            db.soft_delete_notes(own_notes)
        db.delete_category(app.current_category_id)

        app.current_category_id = None
        self.load_categories()
        self.load_notes()

    # --- Tags & Attachments ---

    def manage_tags(self) -> None:
        if self.app.current_note_id is None:
            return
        TagManagerDialog(self.app, self.app.current_note_id)
        self.display_note(self.app.current_note_id)
        self.load_categories()

    def manage_attachments(self) -> None:
        if self.app.current_note_id is None:
            return
        AttachmentDialog(self.app, self.app.current_note_id)
        self.display_note(self.app.current_note_id)

    # --- Version History ---

    def show_versions(self) -> None:
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if not note:
            return
        if note["is_encrypted"]:
            QMessageBox.information(app, "Info", "La cronologia versioni non e' disponibile per le note criptate.")
            return
        content = app.text_editor.toPlainText()
        db.save_version(app.current_note_id, note["title"], content)
        dlg = VersionHistoryDialog(app, app.current_note_id)
        if dlg.result:
            self.display_note(app.current_note_id)

    # --- Inline Decrypt ---

    def _inline_decrypt(self) -> None:
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

    def encrypt_note(self) -> None:
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if note is None:
            return
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

    def decrypt_note(self) -> None:
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if note is None:
            return
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
                app,
                "Decripta",
                "Nota decriptata!\n\nSi = Rimuovi crittografia permanentemente\n"
                "No = Visualizza solo (resta criptata)\nAnnulla = Chiudi",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if btn == QMessageBox.StandardButton.Yes:
                db.set_note_encrypted(app.current_note_id, decrypted, False)
                app._decrypted_cache.pop(app.current_note_id, None)
            elif btn == QMessageBox.StandardButton.No:
                app._decrypted_cache[app.current_note_id] = decrypted
            else:
                return
            self.display_note(app.current_note_id)
