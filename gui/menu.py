"""Menu bar and keyboard shortcuts (PySide6)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction, QKeySequence, QShortcut

from version import VERSION

if TYPE_CHECKING:
    from gui import MyNotesApp


def build_menu(app: MyNotesApp) -> None:
    menubar = app.menuBar()

    # --- File ---
    file_menu = menubar.addMenu("File")
    file_menu.addAction(_action(app, "Nuova Nota", lambda: app.notes_ctl.new_note(), "Ctrl+N"))
    file_menu.addAction(_action(app, "Salva", lambda: app.notes_ctl.save_current(), "Ctrl+S"))
    file_menu.addAction(_action(app, "Elimina Nota", lambda: app.notes_ctl.delete_note(), "Del"))
    file_menu.addSeparator()
    file_menu.addAction(_action(app, "Esporta nota HTML...", lambda: app.export_ctl.export_html(), "Ctrl+E"))
    file_menu.addAction(_action(app, "Esporta nota PDF...", lambda: app.export_ctl.export_pdf(), "Ctrl+Shift+E"))
    file_menu.addAction(_action(app, "Esporta tutte (HTML)...", lambda: app.export_ctl.export_all_html()))
    file_menu.addSeparator()
    file_menu.addAction(_action(app, "Condividi nota (.mynote)...", lambda: app.export_ctl.export_mynote()))
    file_menu.addAction(_action(app, "Importa nota (.mynote)...", lambda: app.export_ctl.import_mynote()))
    file_menu.addAction(_action(app, "Importa Markdown (.md)...", lambda: app.export_ctl.import_markdown()))
    file_menu.addSeparator()
    file_menu.addAction(_action(app, "Esci", lambda: app.close(), "Ctrl+Q"))

    # --- Categorie ---
    cat_menu = menubar.addMenu("Categorie")
    cat_menu.addAction(_action(app, "Nuova Categoria", lambda: app.notes_ctl.new_category(), "Ctrl+Shift+N"))
    cat_menu.addAction(
        _action(
            app,
            "Nuova Sottocategoria",
            lambda: app.notes_ctl.new_subcategory(app.current_category_id) if app.current_category_id else None,
        )
    )
    cat_menu.addAction(_action(app, "Rinomina Categoria", lambda: app.notes_ctl.rename_category(), "F2"))
    cat_menu.addAction(_action(app, "Elimina Categoria", lambda: app.notes_ctl.delete_category()))
    cat_menu.addAction(_action(app, "Svuota Categoria", lambda: app.notes_ctl.empty_category()))

    # --- Nota ---
    note_menu = menubar.addMenu("Nota")
    note_menu.addAction(
        _action(
            app,
            "Apri in finestra separata",
            lambda: app.open_in_window(app.current_note_id) if app.current_note_id else None,
            "Ctrl+O",
        )
    )
    note_menu.addSeparator()
    note_menu.addAction(_action(app, "Fissa/Sgancia nota", lambda: app.notes_ctl.toggle_pin(), "Ctrl+P"))
    note_menu.addAction(_action(app, "Preferita/Non preferita", lambda: app.notes_ctl.toggle_favorite(), "Ctrl+D"))
    note_menu.addSeparator()
    note_menu.addAction(_action(app, "Gestisci Tag", lambda: app.notes_ctl.manage_tags(), "Ctrl+T"))
    note_menu.addAction(_action(app, "Allegati", lambda: app.notes_ctl.manage_attachments()))
    note_menu.addAction(_action(app, "Cronologia versioni", lambda: app.notes_ctl.show_versions(), "Ctrl+H"))
    note_menu.addSeparator()
    note_menu.addAction(_action(app, "Cripta nota...", lambda: app.notes_ctl.encrypt_note()))
    note_menu.addAction(_action(app, "Decripta nota...", lambda: app.notes_ctl.decrypt_note()))
    note_menu.addSeparator()
    note_menu.addAction(_action(app, "Preview Markdown", lambda: app.notes_ctl.toggle_preview(), "Ctrl+M"))
    note_menu.addAction(_action(app, "Inserisci checklist", lambda: app.notes_ctl.insert_checklist(), "Ctrl+L"))
    note_menu.addSeparator()
    note_menu.addAction(_action(app, "Registra audio...", lambda: app.media_ctl.record_audio(), "Ctrl+Shift+A"))
    note_menu.addAction(_action(app, "Importa audio...", lambda: app.media_ctl.import_audio()))
    note_menu.addSeparator()
    note_menu.addAction(_action(app, "Screenshot intero", lambda: app.media_ctl.take_screenshot(), "Ctrl+Shift+S"))
    note_menu.addAction(
        _action(app, "Screenshot regione", lambda: app.media_ctl.take_screenshot_region(), "Ctrl+Shift+R")
    )
    note_menu.addAction(_action(app, "Inserisci immagine...", lambda: app.media_ctl.insert_image(), "Ctrl+I"))

    # --- Backup ---
    backup_menu = menubar.addMenu("Backup")
    backup_menu.addAction(_action(app, "Backup ora", lambda: app.backup_ctl.do_backup(), "Ctrl+B"))
    backup_menu.addAction(_action(app, "Backup Google Drive", lambda: app.backup_ctl.do_gdrive_backup()))
    backup_menu.addSeparator()
    backup_menu.addAction(_action(app, "Ripristina backup...", lambda: app.backup_ctl.do_restore()))
    backup_menu.addSeparator()
    backup_menu.addAction(_action(app, "Impostazioni backup...", lambda: app.backup_ctl.open_settings()))

    # --- Aiuto ---
    help_menu = menubar.addMenu("Aiuto")
    help_menu.addAction(_action(app, "Controlla aggiornamenti...", lambda: app.update_ctl.check()))
    help_menu.addSeparator()
    ver_action = help_menu.addAction(f"MyNotes v{VERSION}")
    ver_action.setEnabled(False)

    # Standalone shortcuts (Ctrl+F, Escape)
    QShortcut(QKeySequence("Ctrl+F"), app, lambda: app.notes_ctl.focus_search())
    QShortcut(QKeySequence("Escape"), app, lambda: app.notes_ctl.clear_search())


def _action(parent: MyNotesApp, text: str, callback: Callable[..., object], shortcut: str | None = None) -> QAction:
    """Helper to create a QAction with optional shortcut."""
    action = QAction(text, parent)
    action.triggered.connect(callback)
    if shortcut:
        action.setShortcut(QKeySequence(shortcut))
    return action
