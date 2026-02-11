"""Finestra dedicata per editing di una nota singola (PySide6)."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextBrowser,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QCloseEvent, QMouseEvent, QPixmap

    from gui import MyNotesApp

import contextlib

import crypto_utils
import database as db
import image_utils
import platform_utils
from annotator import AnnotationTool
from dialogs import AttachmentDialog, AudioRecordDialog, PasswordDialog, TagManagerDialog, VersionHistoryDialog
from gui.constants import (
    AUTO_SAVE_MS,
    BG_DARK,
    BG_ELEVATED,
    BG_SURFACE,
    BORDER,
    FG_PRIMARY,
    FG_SECONDARY,
    FONT_BASE,
    FONT_LG,
    FONT_SM,
    FONT_XL,
    FONT_XS,
    MONO_FONT,
    UI_FONT,
    VERSION_SAVE_EVERY,
)
from gui.formatting import (
    apply_audio_formatting,
    apply_checklist_formatting,
    insert_md_code_block,
    insert_md_horizontal_rule,
    insert_md_line_prefix,
    insert_md_link,
    insert_md_wrap,
)
from gui.widgets import ChecklistEditor


class NoteWindow(QMainWindow):
    """Finestra indipendente per editing di una nota."""

    def __init__(self, parent_app: MyNotesApp, note_id: int, *, decrypted_entry: tuple[str, str] | None = None) -> None:
        super().__init__(parent_app)
        self.app: MyNotesApp = parent_app
        self.note_id: int = note_id
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # State
        self._save_job: QTimer | None = None
        self._image_refs: list[Any] = []
        self._decrypted_cache: dict[int, tuple[str, str]] = {}  # note_id -> (text, password)
        if decrypted_entry is not None:
            self._decrypted_cache[note_id] = decrypted_entry
        self._version_counter: int = 0
        self.gallery_labels: list[QLabel] = []
        self.selected_image_index: int | None = None
        self.gallery_attachments: list[Any] = []
        self._gallery_load_id: int | None = None
        self._closing: bool = False
        self.notes_ctl: NoteWindow = self  # Proxy so ChecklistEditor can call notes_ctl methods

        self.resize(900, 650)
        self.setMinimumSize(700, 450)

        self._build_ui()
        self._display_note()
        self.editor_tabs.setCurrentIndex(1)

    # --- UI ---

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Toolbar
        toolbar = QToolBar("Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Dropdown "Nota"
        note_btn = QPushButton("Nota \u25be")
        note_menu = QMenu(note_btn)
        note_menu.addAction("Fissa/Sgancia", self.toggle_pin)
        note_menu.addAction("Preferita", self.toggle_favorite)
        note_menu.addSeparator()
        note_menu.addAction("Tag...", self.manage_tags)
        note_menu.addAction("Allegati...", self.manage_attachments)
        note_menu.addAction("Cronologia versioni...", self.show_versions)
        note_menu.addSeparator()
        note_menu.addAction("Cripta nota...", self.encrypt_note)
        note_menu.addAction("Decripta nota...", self.decrypt_note)
        note_btn.setMenu(note_menu)
        toolbar.addWidget(note_btn)

        # Dropdown "Inserisci"
        ins_btn = QPushButton("Inserisci \u25be")
        ins_menu = QMenu(ins_btn)
        ins_menu.addAction("Screenshot intero", self.take_screenshot)
        ins_menu.addAction("Screenshot regione", self.take_screenshot_region)
        ins_menu.addAction("Immagine...", self.insert_image)
        ins_menu.addSeparator()
        ins_menu.addAction("Checklist", self.insert_checklist)
        ins_menu.addSeparator()
        ins_menu.addAction("Registra audio...", self.record_audio)
        ins_menu.addAction("Importa audio...", self.import_audio)
        ins_btn.setMenu(ins_menu)
        toolbar.addWidget(ins_btn)

        # Markdown formatting buttons
        toolbar.addSeparator()
        self._add_fmt_btn(toolbar, "G", "Grassetto", lambda: insert_md_wrap(self.text_editor, "**", "**"))
        self._add_fmt_btn(toolbar, "I", "Corsivo", lambda: insert_md_wrap(self.text_editor, "*", "*"))
        self._add_fmt_btn(toolbar, "S", "Barrato", lambda: insert_md_wrap(self.text_editor, "~~", "~~"))
        self._add_fmt_btn(toolbar, "`", "Codice inline", lambda: insert_md_wrap(self.text_editor, "`", "`"))
        toolbar.addSeparator()
        self._add_fmt_btn(toolbar, "H1", "Titolo 1", lambda: insert_md_line_prefix(self.text_editor, "# "))
        self._add_fmt_btn(toolbar, "H2", "Titolo 2", lambda: insert_md_line_prefix(self.text_editor, "## "))
        self._add_fmt_btn(toolbar, "H3", "Titolo 3", lambda: insert_md_line_prefix(self.text_editor, "### "))
        toolbar.addSeparator()
        self._add_fmt_btn(toolbar, "Link", "Link", lambda: insert_md_link(self.text_editor))
        self._add_fmt_btn(toolbar, "\u2022", "Lista puntata", lambda: insert_md_line_prefix(self.text_editor, "- "))
        self._add_fmt_btn(toolbar, "1.", "Lista numerata", lambda: insert_md_line_prefix(self.text_editor, "1. "))
        self._add_fmt_btn(toolbar, ">", "Citazione", lambda: insert_md_line_prefix(self.text_editor, "> "))
        self._add_fmt_btn(toolbar, "{ }", "Blocco codice", lambda: insert_md_code_block(self.text_editor))
        self._add_fmt_btn(toolbar, "---", "Linea orizzontale", lambda: insert_md_horizontal_rule(self.text_editor))

        toolbar.addSeparator()
        self._preview_btn = QPushButton("Anteprima")
        self._preview_btn.setToolTip("Alterna Modifica / Anteprima (Ctrl+M)")
        self._preview_btn.setStyleSheet("font-weight: bold; padding: 2px 10px;")
        self._preview_btn.clicked.connect(self._toggle_preview)
        toolbar.addWidget(self._preview_btn)

        # Editor area
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(10, 8, 10, 10)
        editor_layout.setSpacing(2)

        # Title
        self.title_entry = QLineEdit()
        self.title_entry.setFont(QFont(UI_FONT, FONT_XL, QFont.Weight.Bold))
        self.title_entry.setStyleSheet(
            f"border: none; background: transparent; padding: 8px; font-size: {FONT_XL}pt; font-weight: bold;"
        )
        self.title_entry.textChanged.connect(self.schedule_save)
        editor_layout.addWidget(self.title_entry)

        # Meta + Tags
        self.meta_label = QLabel("")
        self.meta_label.setStyleSheet(f"color: {FG_SECONDARY}; font-size: {FONT_SM}pt; padding: 0px 12px;")
        editor_layout.addWidget(self.meta_label)
        self.tags_label = QLabel("")
        self.tags_label.setStyleSheet(f"color: {FG_SECONDARY}; font-size: {FONT_SM}pt; padding: 2px 12px;")
        editor_layout.addWidget(self.tags_label)

        # Editor + Gallery splitter
        editor_splitter = QSplitter(Qt.Orientation.Vertical)
        editor_layout.addWidget(editor_splitter)

        # Text editor + Preview tabs
        self.editor_tabs = QTabWidget()
        self.editor_tabs.setTabPosition(QTabWidget.TabPosition.South)

        self.text_editor = ChecklistEditor()
        self.text_editor.set_app(self)
        self.text_editor.setFont(QFont(MONO_FONT, FONT_LG))
        self.text_editor.textChanged.connect(self.schedule_save)
        self.editor_tabs.addTab(self.text_editor, "Modifica")

        self.preview_browser = QTextBrowser()
        self.preview_browser.setOpenExternalLinks(True)
        self.editor_tabs.addTab(self.preview_browser, "Preview")

        self.editor_tabs.currentChanged.connect(self._on_tab_changed)

        editor_splitter.addWidget(self.editor_tabs)

        # Gallery
        gallery_widget = QWidget()
        gallery_layout = QVBoxLayout(gallery_widget)
        gallery_layout.setContentsMargins(0, 0, 0, 0)
        gallery_layout.setSpacing(2)

        gallery_header = QWidget()
        gallery_header_layout = QHBoxLayout(gallery_header)
        gallery_header_layout.setContentsMargins(5, 2, 5, 2)
        gallery_header_layout.addWidget(QLabel("Immagini allegate"))
        gallery_header_layout.addStretch()
        remove_btn = QPushButton("Rimuovi")
        remove_btn.clicked.connect(self.remove_selected)
        gallery_header_layout.addWidget(remove_btn)
        open_btn = QPushButton("Apri")
        open_btn.clicked.connect(self.open_selected)
        gallery_header_layout.addWidget(open_btn)
        annotate_btn = QPushButton("Annota")
        annotate_btn.clicked.connect(self.annotate_selected)
        gallery_header_layout.addWidget(annotate_btn)
        gallery_layout.addWidget(gallery_header)

        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setMinimumHeight(80)
        self.gallery_scroll.setMaximumHeight(150)
        self.gallery_inner = QWidget()
        self.gallery_inner_layout = QHBoxLayout(self.gallery_inner)
        self.gallery_inner_layout.setContentsMargins(4, 4, 4, 4)
        self.gallery_inner_layout.setSpacing(6)
        self.gallery_inner_layout.addStretch()
        self.gallery_scroll.setWidget(self.gallery_inner)
        gallery_layout.addWidget(self.gallery_scroll)

        editor_splitter.addWidget(gallery_widget)
        editor_splitter.setStretchFactor(0, 3)
        editor_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(editor_widget)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Pronto")

        # Shortcuts
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_current)
        QShortcut(QKeySequence("Ctrl+T"), self, self.manage_tags)
        QShortcut(QKeySequence("Ctrl+H"), self, self.show_versions)
        QShortcut(QKeySequence("Ctrl+P"), self, self.toggle_pin)
        QShortcut(QKeySequence("Ctrl+D"), self, self.toggle_favorite)
        QShortcut(QKeySequence("Ctrl+L"), self, self.insert_checklist)
        QShortcut(QKeySequence("Ctrl+I"), self, self.insert_image)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self.take_screenshot)
        QShortcut(QKeySequence("Ctrl+Shift+R"), self, self.take_screenshot_region)
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, self.record_audio)
        QShortcut(QKeySequence("Ctrl+M"), self, self._toggle_preview)
        QShortcut(QKeySequence("Ctrl+B"), self, lambda: insert_md_wrap(self.text_editor, "**", "**"))
        QShortcut(QKeySequence("Ctrl+W"), self, self._on_close)

    # --- Toolbar / Preview helpers ---

    def _add_fmt_btn(self, toolbar: QToolBar, label: str, tooltip: str, callback: Callable[[], None]) -> QPushButton:
        """Create a compact formatting button and add it to *toolbar*."""
        btn = QPushButton(label)
        btn.setToolTip(tooltip)
        btn.setFixedSize(32, 26)
        btn.setStyleSheet("font-size: 10pt; padding: 0px;")
        btn.clicked.connect(callback)
        toolbar.addWidget(btn)
        return btn

    def _update_preview(self) -> None:
        """Render markdown content to HTML in the preview tab."""
        import markdown

        content = self.text_editor.toPlainText()
        html = markdown.markdown(content, extensions=["fenced_code", "tables", "nl2br"])
        styled = (
            f"<div style=\"font-family: '{UI_FONT}', sans-serif; "
            f"color: {FG_PRIMARY}; background-color: {BG_DARK}; "
            f'font-size: {FONT_BASE + 1}pt; line-height: 1.6;">'
            f"{html}</div>"
        )
        self.preview_browser.setHtml(styled)

    def _toggle_preview(self) -> None:
        """Toggle between edit and preview tabs."""
        tabs = self.editor_tabs
        tabs.setCurrentIndex(1 if tabs.currentIndex() == 0 else 0)

    def _on_tab_changed(self, index: int) -> None:
        """Update preview content and toggle button label on tab switch."""
        if index == 1:
            self._update_preview()
        self._preview_btn.setText("Modifica" if index == 1 else "Anteprima")

    # --- Display ---

    def _display_note(self) -> None:
        note = db.get_note(self.note_id)
        if not note:
            self.setWindowTitle("Nota non trovata")
            return

        self.setWindowTitle(f"{note['title']} - MyNotes")

        self.title_entry.blockSignals(True)
        self.title_entry.setText(note["title"])
        self.title_entry.blockSignals(False)

        self.text_editor.setReadOnly(False)
        self.text_editor.blockSignals(True)
        self.text_editor.clear()

        if note["is_encrypted"]:
            if self.note_id in self._decrypted_cache:
                self.text_editor.setPlainText(self._decrypted_cache[self.note_id][0])
            else:
                self.text_editor.setPlainText("[Nota criptata - usa Nota > Decripta nota...]")
                self.text_editor.setReadOnly(True)
        else:
            self.text_editor.setPlainText(note["content"] or "")
            self._apply_checklist_formatting()
            self._apply_audio_formatting()

        self.text_editor.blockSignals(False)

        if self.editor_tabs.currentIndex() == 1:
            self._update_preview()

        created = note["created_at"][:16].replace("T", " ")
        updated = note["updated_at"][:16].replace("T", " ")
        meta = f"Creata: {created}  |  Modificata: {updated}"
        if note["is_pinned"]:
            meta += "  |  Fissata"
        if note["is_favorite"]:
            meta += "  |  Preferita"
        if note["is_encrypted"]:
            meta += "  |  Criptata"
        self.meta_label.setText(meta)

        tags = db.get_note_tags(self.note_id)
        tag_str = "Tag: " + ", ".join(f"#{t['name']}" for t in tags) if tags else "Nessun tag"
        att_count = len(db.get_note_attachments(self.note_id))
        if att_count > 0:
            tag_str += f"  |  {att_count} allegato/i"
        self.tags_label.setText(tag_str)

        self._load_gallery()

    # --- Auto-save ---

    def schedule_save(self) -> None:
        if self._save_job:
            self._save_job.stop()
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self.save_current)
        timer.start(AUTO_SAVE_MS)
        self._save_job = timer

    def save_current(self) -> None:
        self._save_job = None
        if self.text_editor.isReadOnly():
            return
        note = db.get_note(self.note_id)
        if not note:
            return
        if note["is_encrypted"] and self.note_id not in self._decrypted_cache:
            return

        title = self.title_entry.text().strip()
        content = self.text_editor.toPlainText()
        if not title:
            return

        if not note["is_encrypted"]:
            self._version_counter += 1
            if self._version_counter >= VERSION_SAVE_EVERY:
                self._version_counter = 0
                db.save_version(self.note_id, title, content)

        if note["is_encrypted"] and self.note_id in self._decrypted_cache:
            password = self._decrypted_cache[self.note_id][1]
            encrypted = crypto_utils.encrypt(content, password)
            db.set_note_encrypted(self.note_id, encrypted, True)
            self._decrypted_cache[self.note_id] = (content, password)
        else:
            db.update_note(self.note_id, title=title, content=content)

        self.setWindowTitle(f"{title} - MyNotes")
        self.status_bar.showMessage("Salvato")

    # --- Checklist / Audio ---

    def _apply_checklist_formatting(self) -> None:
        apply_checklist_formatting(self.text_editor)

    def _apply_audio_formatting(self) -> None:
        apply_audio_formatting(self.text_editor)

    def insert_checklist(self) -> None:
        cursor = self.text_editor.textCursor()
        cursor.insertText("\n[ ] Elemento da fare\n[ ] Altro elemento\n[x] Elemento completato\n")
        self._apply_checklist_formatting()

    def _insert_audio_marker(self, att_filename: str, description: str) -> None:
        desc = description or "audio"
        marker = f"\n[♪:{att_filename} {desc}]\n"
        cursor = self.text_editor.textCursor()
        cursor.insertText(marker)
        self._apply_audio_formatting()
        self._apply_checklist_formatting()
        self.schedule_save()

    # --- Gallery ---

    def _load_gallery(self) -> None:
        self._image_refs.clear()
        self.gallery_labels.clear()
        self.selected_image_index = None
        self._gallery_load_id = self.note_id

        layout = self.gallery_inner_layout
        while layout.count() > 0:
            child = layout.takeAt(0)
            if child is not None and child.widget():
                child.widget().deleteLater()  # type: ignore[union-attr]

        attachments = db.get_note_attachments(self.note_id)
        self.gallery_attachments = [a for a in attachments if image_utils.is_image_file(a["original_name"])]

        if not self.gallery_attachments:
            no_img = QLabel("Nessuna immagine")
            no_img.setStyleSheet(f"color: {FG_SECONDARY}; padding: 20px;")
            layout.addWidget(no_img)
            layout.addStretch()
            return

        items: list[tuple[int, Any, str, QLabel | None]] = []
        for i, att in enumerate(self.gallery_attachments):
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
            lbl.mousePressEvent = lambda e, idx=i, lbl_ref=lbl: self._on_gallery_click(e, idx, lbl_ref)  # type: ignore[method-assign,misc]
            lbl.mouseDoubleClickEvent = lambda e, idx=i: self._open_image(idx)  # type: ignore[method-assign,misc]
            frame_layout.addWidget(lbl)

            name_label = QLabel(att["original_name"][:15])
            name_label.setStyleSheet(f"color: {FG_SECONDARY}; font-size: {FONT_XS}pt;")
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame_layout.addWidget(name_label)

            layout.addWidget(frame)
            self.gallery_labels.append(lbl)
            items.append((i, att, path, lbl))

        layout.addStretch()

        def _load_thumbs() -> None:
            for _i, _att, path, lbl in items:
                if self._gallery_load_id != self.note_id:
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
        self._image_refs.append(pixmap)
        label.setPixmap(pixmap)
        label.setFixedSize(pixmap.width() + 4, pixmap.height() + 4)

    def _on_gallery_click(self, event: QMouseEvent, index: int, label: QLabel) -> None:
        self._select_image(index, label)

    def _select_image(self, index: int, label: QLabel) -> None:
        for lbl in self.gallery_labels:
            lbl.setStyleSheet(f"background-color: {BG_SURFACE}; border: 2px solid transparent;")
        label.setStyleSheet(f"background-color: {BG_SURFACE}; border: 2px solid {BORDER};")
        self.selected_image_index = index

    def _open_image(self, index: int) -> None:
        att = self.gallery_attachments[index]
        platform_utils.open_file(os.path.join(db.ATTACHMENTS_DIR, att["filename"]))

    def open_selected(self) -> None:
        if self.selected_image_index is not None:
            self._open_image(self.selected_image_index)

    def remove_selected(self) -> None:
        if self.selected_image_index is None:
            return
        att = self.gallery_attachments[self.selected_image_index]
        answer = QMessageBox.question(self, "Conferma", f"Rimuovere '{att['original_name']}'?")
        if answer == QMessageBox.StandardButton.Yes:
            db.delete_attachment(att["id"])
            self._display_note()

    def annotate_selected(self) -> None:
        if self.selected_image_index is None:
            QMessageBox.information(self, "Info", "Seleziona un'immagine dalla galleria.")
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

    # --- Media ---

    def take_screenshot(self) -> None:
        self.hide()
        QTimer.singleShot(500, lambda: self._do_screenshot(full=True))

    def take_screenshot_region(self) -> None:
        self.hide()
        QTimer.singleShot(500, lambda: self._do_screenshot(full=False))

    def _do_screenshot(self, full: bool = True) -> None:
        import uuid

        filename = f"screenshot_{uuid.uuid4().hex[:8]}.png"
        save_path = os.path.join(db.ATTACHMENTS_DIR, filename)
        try:
            success = (
                platform_utils.take_screenshot(save_path) if full else platform_utils.take_screenshot_region(save_path)
            )
        except Exception:
            success = False
        self.show()
        if success and os.path.exists(save_path):
            now = datetime.now().isoformat()
            with db._connect() as conn:
                conn.execute(
                    "INSERT INTO attachments (note_id, filename, original_name, added_at) VALUES (?, ?, ?, ?)",
                    (self.note_id, filename, filename, now),
                )
                conn.commit()
            self._display_note()
            self.status_bar.showMessage("Screenshot catturato!")
        else:
            msg = "Impossibile catturare lo screenshot.\n"
            if platform_utils.IS_LINUX:
                msg += "Installa: sudo dnf install grim slurp"
            QMessageBox.warning(self, "Screenshot", msg)

    def insert_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona immagine", "", "Immagini (*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.webp);;Tutti (*.*)"
        )
        if path:
            db.add_attachment(self.note_id, path)
            self._display_note()
            self.status_bar.showMessage("Immagine aggiunta")

    def record_audio(self) -> None:
        dlg = AudioRecordDialog(self, mode="record")
        if dlg.result is None:
            return
        temp_path = dlg.result["path"]
        description = dlg.result["description"]
        att_filename = db.add_attachment(self.note_id, temp_path)
        with contextlib.suppress(OSError):
            os.remove(temp_path)
        self._insert_audio_marker(att_filename, description)
        self._display_note()
        self.status_bar.showMessage("Audio registrato")

    def import_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona file audio", "", "Audio (*.mp3 *.wav *.ogg *.m4a *.flac *.aac *.wma);;Tutti (*.*)"
        )
        if not path:
            return
        dlg = AudioRecordDialog(self, mode="describe", audio_path=path)
        if dlg.result is None:
            return
        description = dlg.result["description"]
        att_filename = db.add_attachment(self.note_id, path)
        self._insert_audio_marker(att_filename, description)
        self._display_note()
        self.status_bar.showMessage("Audio importato")

    # --- Note Actions ---

    def toggle_pin(self) -> None:
        db.toggle_pin(self.note_id)
        self._display_note()
        self.app.notes_ctl.load_notes()

    def toggle_favorite(self) -> None:
        db.toggle_favorite(self.note_id)
        self._display_note()
        self.app.notes_ctl.load_notes()

    def manage_tags(self) -> None:
        TagManagerDialog(self, self.note_id)
        self._display_note()
        self.app.notes_ctl.load_categories()

    def manage_attachments(self) -> None:
        AttachmentDialog(self, self.note_id)
        self._display_note()

    def show_versions(self) -> None:
        note = db.get_note(self.note_id)
        if not note:
            return
        if note["is_encrypted"]:
            QMessageBox.information(self, "Info", "La cronologia versioni non e' disponibile per le note criptate.")
            return
        content = self.text_editor.toPlainText()
        db.save_version(self.note_id, note["title"], content)
        dlg = VersionHistoryDialog(self, self.note_id)
        if dlg.result:
            self._display_note()

    def encrypt_note(self) -> None:
        note = db.get_note(self.note_id)
        if not note:
            return
        if note["is_encrypted"]:
            QMessageBox.information(self, "Info", "La nota e' gia' criptata.")
            return
        dlg = PasswordDialog(self, title="Cripta nota", confirm=True)
        if dlg.result:
            content = self.text_editor.toPlainText()
            encrypted = crypto_utils.encrypt(content, dlg.result)
            db.set_note_encrypted(self.note_id, encrypted, True)
            db.delete_note_versions(self.note_id)
            self._decrypted_cache.pop(self.note_id, None)
            self._display_note()
            self.status_bar.showMessage("Nota criptata")

    def decrypt_note(self) -> None:
        note = db.get_note(self.note_id)
        if not note:
            return
        if not note["is_encrypted"]:
            QMessageBox.information(self, "Info", "La nota non e' criptata.")
            return
        dlg = PasswordDialog(self, title="Decripta nota")
        if dlg.result:
            decrypted = crypto_utils.decrypt(note["content"], dlg.result)
            if decrypted is None:
                QMessageBox.critical(self, "Errore", "Password errata.")
                return
            btn = QMessageBox.question(
                self,
                "Decripta",
                "Nota decriptata!\n\nSi = Rimuovi crittografia permanentemente\n"
                "No = Visualizza solo (resta criptata)\nAnnulla = Chiudi",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if btn == QMessageBox.StandardButton.Yes:
                db.set_note_encrypted(self.note_id, decrypted, False)
                self._decrypted_cache.pop(self.note_id, None)
            elif btn == QMessageBox.StandardButton.No:
                self._decrypted_cache[self.note_id] = (decrypted, dlg.result)
            else:
                return
            self._display_note()

    # --- Lifecycle ---

    def _sync_cache_to_app(self) -> None:
        """Sync decrypted cache back to main app so it shows fresh content."""
        if self.note_id in self._decrypted_cache:
            self.app._decrypted_cache[self.note_id] = self._decrypted_cache[self.note_id]
        else:
            self.app._decrypted_cache.pop(self.note_id, None)

    def _on_close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.save_current()
        self._sync_cache_to_app()
        self.app._detached_windows.pop(self.note_id, None)
        self.app.notes_ctl.load_notes()
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._closing:
            self._closing = True
            self.save_current()
            self._sync_cache_to_app()
            self.app._detached_windows.pop(self.note_id, None)
            self.app.notes_ctl.load_notes()
        event.accept()
