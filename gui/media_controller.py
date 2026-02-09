"""Screenshots, image gallery, annotations, audio (PySide6)."""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import QFileDialog, QFrame, QLabel, QMenu, QMessageBox, QVBoxLayout

import database as db

if TYPE_CHECKING:
    from gui import MyNotesApp
import contextlib

import image_utils
import platform_utils
from annotator import AnnotationTool
from dialogs import AudioRecordDialog
from gui.constants import BG_ELEVATED, BG_SURFACE, BORDER, FG_SECONDARY, FONT_XS


class MediaController:
    def __init__(self, app: MyNotesApp) -> None:
        self.app = app
        self._gallery_load_id: int | None = None

    # --- Gallery ---

    def load_gallery(self, note_id: int) -> None:
        app = self.app
        app._image_refs.clear()
        app.gallery_labels.clear()
        app.selected_image_index = None
        self._gallery_load_id = note_id

        # Clear gallery layout
        layout = app.gallery_inner_layout
        while layout.count() > 0:
            child = layout.takeAt(0)
            if child is not None and child.widget():
                child.widget().deleteLater()  # type: ignore[union-attr]

        attachments = db.get_note_attachments(note_id)
        app.gallery_attachments = [a for a in attachments if image_utils.is_image_file(a["original_name"])]

        if not app.gallery_attachments:
            no_img_label = QLabel("Nessuna immagine")
            no_img_label.setStyleSheet(f"color: {FG_SECONDARY}; padding: 20px;")
            layout.addWidget(no_img_label)
            layout.addStretch()
            return

        items: list[tuple[int, sqlite3.Row, str, QLabel | None]] = []
        for i, att in enumerate(app.gallery_attachments):
            path = os.path.join(db.ATTACHMENTS_DIR, att["filename"])
            if not os.path.exists(path):
                items.append((i, att, path, None))
                continue

            frame = QFrame()
            frame.setStyleSheet(f"background-color: {BG_ELEVATED}; padding: 4px;")
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(4, 4, 4, 4)
            frame_layout.setSpacing(2)

            lbl = QLabel("...")
            lbl.setFixedSize(100, 80)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"background-color: {BG_SURFACE}; border: 2px solid transparent;")
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            lbl.setProperty("gallery_index", i)
            lbl.mousePressEvent = lambda e, idx=i, lbl_ref=lbl: self._on_gallery_click(e, idx, lbl_ref)  # type: ignore[method-assign,misc]
            lbl.mouseDoubleClickEvent = lambda e, idx=i: self._open_image(idx)  # type: ignore[method-assign,misc]
            frame_layout.addWidget(lbl)

            name_label = QLabel(att["original_name"][:15])
            name_label.setStyleSheet(f"color: {FG_SECONDARY}; font-size: {FONT_XS}pt;")
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame_layout.addWidget(name_label)

            layout.addWidget(frame)
            app.gallery_labels.append(lbl)
            items.append((i, att, path, lbl))

        layout.addStretch()

        def _load_thumbs() -> None:
            for _i, _att, path, lbl in items:
                if self._gallery_load_id != note_id:
                    return
                if lbl is None:
                    continue
                try:
                    pixmap = image_utils.load_image_as_pixmap(path, max_width=100, max_height=80)
                    QTimer.singleShot(0, lambda p=pixmap, lbl_ref=lbl: self._set_thumb(p, lbl_ref))
                except Exception:
                    continue

        threading.Thread(target=_load_thumbs, daemon=True).start()

    def _set_thumb(self, pixmap: QPixmap, label: QLabel) -> None:
        self.app._image_refs.append(pixmap)
        label.setPixmap(pixmap)
        label.setFixedSize(pixmap.width() + 4, pixmap.height() + 4)

    def _on_gallery_click(self, event: QMouseEvent, index: int, label: QLabel) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._select_image(index, label)
            self._show_gallery_context_menu(event, index, label)
        elif event.button() == Qt.MouseButton.LeftButton:
            self._select_image(index, label)

    def _select_image(self, index: int, label: QLabel) -> None:
        for lbl in self.app.gallery_labels:
            lbl.setStyleSheet(f"background-color: {BG_SURFACE}; border: 2px solid transparent;")
        label.setStyleSheet(f"background-color: {BG_SURFACE}; border: 2px solid {BORDER};")
        self.app.selected_image_index = index

    def _show_gallery_context_menu(self, event: QMouseEvent, index: int, label: QLabel) -> None:
        menu = QMenu(self.app)
        menu.addAction("Apri", lambda: self._open_image(index))
        menu.addAction("Annota", self.annotate_selected)
        menu.addSeparator()
        menu.addAction("Rimuovi", self.remove_selected)
        menu.popup(label.mapToGlobal(event.pos()))

    def _open_image(self, index: int) -> None:
        att = self.app.gallery_attachments[index]
        platform_utils.open_file(os.path.join(db.ATTACHMENTS_DIR, att["filename"]))

    def open_selected(self) -> None:
        if self.app.selected_image_index is not None:
            self._open_image(self.app.selected_image_index)

    def remove_selected(self) -> None:
        app = self.app
        if app.selected_image_index is None:
            return
        att = app.gallery_attachments[app.selected_image_index]
        reply = QMessageBox.question(app, "Conferma", f"Rimuovere '{att['original_name']}'?")
        if reply == QMessageBox.StandardButton.Yes:
            db.delete_attachment(att["id"])
            if app.current_note_id:
                self.load_gallery(app.current_note_id)
                app.notes_ctl.display_note(app.current_note_id)

    def annotate_selected(self) -> None:
        app = self.app
        if app.selected_image_index is None:
            QMessageBox.information(app, "Info", "Seleziona un'immagine dalla galleria.")
            return
        att = app.gallery_attachments[app.selected_image_index]
        path = os.path.join(db.ATTACHMENTS_DIR, att["filename"])
        if not os.path.exists(path):
            return
        tool = AnnotationTool(app, path)
        if tool.result_path and os.path.exists(tool.result_path) and app.current_note_id is not None:
            db.add_attachment(app.current_note_id, tool.result_path)
            os.remove(tool.result_path)
            self.load_gallery(app.current_note_id)
            app.notes_ctl.display_note(app.current_note_id)

    # --- Screenshots ---

    def take_screenshot(self) -> None:
        if self.app.current_note_id is None:
            QMessageBox.information(self.app, "Info", "Crea o seleziona una nota prima.")
            return
        self.app.hide()
        QTimer.singleShot(500, lambda: self._do_screenshot(full=True))

    def take_screenshot_region(self) -> None:
        if self.app.current_note_id is None:
            QMessageBox.information(self.app, "Info", "Crea o seleziona una nota prima.")
            return
        self.app.hide()
        QTimer.singleShot(500, lambda: self._do_screenshot(full=False))

    def _do_screenshot(self, full: bool = True) -> None:
        import uuid

        app = self.app
        filename = f"screenshot_{uuid.uuid4().hex[:8]}.png"
        save_path = os.path.join(db.ATTACHMENTS_DIR, filename)
        try:
            success = (
                platform_utils.take_screenshot(save_path) if full else platform_utils.take_screenshot_region(save_path)
            )
        except Exception:
            success = False
        app.show()
        if success and os.path.exists(save_path) and app.current_note_id is not None:
            now = datetime.now().isoformat()
            with db._connect() as conn:
                conn.execute(
                    "INSERT INTO attachments (note_id, filename, original_name, added_at) VALUES (?, ?, ?, ?)",
                    (app.current_note_id, filename, filename, now),
                )
                conn.commit()
            app.notes_ctl.display_note(app.current_note_id)
            app.statusBar().showMessage("Screenshot catturato!")
        else:
            msg = "Impossibile catturare lo screenshot.\n"
            if platform_utils.IS_LINUX:
                msg += "Installa: sudo dnf install grim slurp"
            QMessageBox.warning(app, "Screenshot", msg)

    def insert_image(self) -> None:
        app = self.app
        if app.current_note_id is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            app, "Seleziona immagine", "", "Immagini (*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.webp);;Tutti (*.*)"
        )
        if path:
            db.add_attachment(app.current_note_id, path)
            app.notes_ctl.display_note(app.current_note_id)
            app.statusBar().showMessage("Immagine aggiunta")

    # --- Audio ---

    def record_audio(self) -> None:
        app = self.app
        if app.current_note_id is None:
            QMessageBox.information(app, "Info", "Crea o seleziona una nota prima.")
            return

        dlg = AudioRecordDialog(app, mode="record")
        if dlg.result is None:
            return

        temp_path = dlg.result["path"]
        description = dlg.result["description"]

        att_filename = db.add_attachment(app.current_note_id, temp_path)
        with contextlib.suppress(OSError):
            os.remove(temp_path)

        app.notes_ctl.insert_audio_marker(att_filename, description)
        app.notes_ctl.display_note(app.current_note_id)
        app.statusBar().showMessage("Audio registrato")

    def import_audio(self) -> None:
        app = self.app
        if app.current_note_id is None:
            QMessageBox.information(app, "Info", "Crea o seleziona una nota prima.")
            return

        path, _ = QFileDialog.getOpenFileName(
            app, "Seleziona file audio", "", "Audio (*.mp3 *.wav *.ogg *.m4a *.flac *.aac *.wma);;Tutti (*.*)"
        )
        if not path:
            return

        dlg = AudioRecordDialog(app, mode="describe", audio_path=path)
        if dlg.result is None:
            return

        description = dlg.result["description"]
        att_filename = db.add_attachment(app.current_note_id, path)

        app.notes_ctl.insert_audio_marker(att_filename, description)
        app.notes_ctl.display_note(app.current_note_id)
        app.statusBar().showMessage("Audio importato")
