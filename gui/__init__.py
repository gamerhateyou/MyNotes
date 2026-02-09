"""MyNotes GUI - Main application window (PySide6)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import sqlite3

    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import (
        QComboBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QScrollArea,
        QStackedWidget,
        QTabWidget,
        QTextBrowser,
        QWidget,
    )

    from gui.widgets import CategoryList, ChecklistEditor, DraggableNoteList

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow

import backup_utils
from gui.backup_controller import BackupController
from gui.constants import (
    ACCENT,
    BG_DARK,
    BG_ELEVATED,
    BG_SURFACE,
    BORDER,
    BORDER_LIGHT,
    FG_PRIMARY,
    FG_SECONDARY,
    FONT_BASE,
    MONO_FONT,
    SELECT_BG,
    SELECT_FG,
)
from gui.export_controller import ExportController
from gui.layout import build_main_layout, build_toolbar
from gui.media_controller import MediaController
from gui.menu import build_menu
from gui.note_controller import NoteController
from gui.update_controller import UpdateController
from version import VERSION

log = logging.getLogger("app")


class MyNotesApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"MyNotes v{VERSION} by homelabz")
        self.resize(1200, 750)
        self.setMinimumSize(900, 550)

        # State
        self.current_note_id: int | None = None
        self.current_category_id: int | None = None
        self.current_tag_id: int | None = None
        self.show_trash: bool = False
        self.show_favorites: bool = False
        self._save_job: QTimer | None = None
        self._image_refs: list[Any] = []
        self._version_counter: int = 0
        self._decrypted_cache: dict[int, str] = {}
        self._detached_windows: dict[int, Any] = {}

        # Data
        self.categories: list[sqlite3.Row] = []
        self.notes: list[sqlite3.Row] = []
        self.all_tags: list[sqlite3.Row] = []
        self.gallery_attachments: list[sqlite3.Row] = []

        # Widgets (set by build_toolbar / build_main_layout)
        self.search_entry: QLineEdit
        self.tag_combo: QComboBox
        self.cat_listbox: CategoryList
        self.note_listbox: DraggableNoteList
        self.list_header: QLabel
        self.title_entry: QLineEdit
        self.text_editor: ChecklistEditor
        self.editor_tabs: QTabWidget
        self.preview_browser: QTextBrowser
        self.meta_label: QLabel
        self.tags_label: QLabel
        self.editor_stack: QStackedWidget
        self.decrypt_entry: QLineEdit
        self.decrypt_btn: QPushButton
        self.decrypt_error_label: QLabel
        self.gallery_scroll: QScrollArea
        self.gallery_inner: QWidget
        self.gallery_inner_layout: QHBoxLayout
        self.selected_image_index: int | None
        self.gallery_labels: list[QLabel]

        # Apply custom QSS on top of qdarktheme
        self._apply_qss()

        # Build UI
        build_menu(self)
        build_toolbar(self)
        build_main_layout(self)

        # Controllers
        self.notes_ctl = NoteController(self)
        self.export_ctl = ExportController(self)
        self.media_ctl = MediaController(self)
        self.backup_ctl = BackupController(self)
        self.update_ctl = UpdateController(self)

        # Backup: migrate legacy password, prompt if needed
        backup_utils.migrate_legacy_password()
        self._backup_scheduler = backup_utils.BackupScheduler(self)
        self._backup_scheduler.start()
        QTimer.singleShot(500, self._check_backup_password)

        # Load data
        self.notes_ctl.load_categories()
        self.notes_ctl.load_notes()

        QTimer.singleShot(2000, self.update_ctl.check_silent)

    def open_in_window(self, note_id: int) -> None:
        if note_id is None:
            return
        if note_id in self._detached_windows:
            win = self._detached_windows[note_id]
            win.raise_()
            win.activateWindow()
            return
        self.notes_ctl.save_current()
        if self.current_note_id == note_id:
            self.notes_ctl._clear_editor()
            self.note_listbox.clearSelection()
        from gui.note_window import NoteWindow

        win = NoteWindow(self, note_id)
        self._detached_windows[note_id] = win
        win.show()

    def _check_backup_password(self) -> None:
        """Se crittografia backup attiva ma password non in memoria, chiedi all'utente."""
        settings = backup_utils.get_settings()
        if settings.get("encrypt_backups") and not backup_utils.has_backup_password():
            from dialogs.password import PasswordDialog

            dlg = PasswordDialog(self, title="Password backup")
            if dlg.result:
                backup_utils.set_backup_password(dlg.result)
            else:
                self.statusBar().showMessage("Crittografia backup disattivata (nessuna password)")
                settings["encrypt_backups"] = False
                backup_utils.save_settings(settings)

    def closeEvent(self, event: QCloseEvent) -> None:
        for win in list(self._detached_windows.values()):
            win._on_close()
        self.notes_ctl.save_current()
        self._backup_scheduler.stop()
        settings = backup_utils.get_settings()
        if settings.get("auto_backup", True):
            if settings.get("encrypt_backups") and not backup_utils.has_backup_password():
                log.warning("Auto-backup: crittografia abilitata ma password non disponibile, salto")
            else:
                try:
                    backup_utils.do_local_backup()
                except Exception as e:
                    log.warning("Auto-backup alla chiusura fallito: %s", e)
        event.accept()

    def _apply_qss(self) -> None:
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {BG_DARK};
            }}
            QListWidget {{
                background-color: {BG_ELEVATED};
                color: {FG_PRIMARY};
                border: none;
                border-right: 1px solid {BORDER};
                font-size: {FONT_BASE}pt;
            }}
            QListWidget::item:selected {{
                background-color: {SELECT_BG};
                color: {SELECT_FG};
            }}
            QPlainTextEdit {{
                background-color: {BG_DARK};
                color: {FG_PRIMARY};
                border: 1px solid {BORDER};
                font-family: "{MONO_FONT}";
                font-size: {FONT_BASE + 1}pt;
                padding: 8px;
            }}
            QLineEdit {{
                background-color: {BG_ELEVATED};
                color: {FG_PRIMARY};
                border: 1px solid {BORDER};
                padding: 4px;
            }}
            QLineEdit:focus {{
                border-color: {ACCENT};
            }}
            QComboBox {{
                background-color: {BG_ELEVATED};
                color: {FG_PRIMARY};
                border: 1px solid {BORDER};
                padding: 4px;
            }}
            QSplitter::handle {{
                background-color: {BORDER_LIGHT};
            }}
            QSplitter::handle:horizontal {{
                width: 2px;
            }}
            QSplitter::handle:vertical {{
                height: 2px;
            }}
            QToolBar {{
                background-color: {BG_SURFACE};
                border-bottom: 1px solid {BORDER};
                spacing: 6px;
                padding: 6px;
            }}
            QMenuBar {{
                background-color: {BG_SURFACE};
                color: {FG_PRIMARY};
            }}
            QMenuBar::item:selected {{
                background-color: {SELECT_BG};
            }}
            QMenu {{
                background-color: {BG_ELEVATED};
                color: {FG_PRIMARY};
                border: 1px solid {BORDER};
            }}
            QMenu::item:selected {{
                background-color: {SELECT_BG};
                color: {SELECT_FG};
            }}
            QStatusBar {{
                background-color: {BG_SURFACE};
                color: {FG_SECONDARY};
            }}
            QScrollArea {{
                background-color: {BG_ELEVATED};
                border: 1px solid {BORDER};
                border-radius: 4px;
            }}
            QPushButton {{
                background-color: {BG_ELEVATED};
                color: {FG_PRIMARY};
                border: 1px solid {BORDER};
                padding: 5px 14px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {BORDER_LIGHT};
                border-color: {ACCENT};
            }}
            QPushButton:pressed {{
                background-color: {BORDER};
            }}
            QPushButton::menu-indicator {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                right: 6px;
                width: 10px;
            }}
            QLabel {{
                color: {FG_PRIMARY};
            }}
            QTextBrowser {{
                background-color: {BG_DARK};
                color: {FG_PRIMARY};
                border: none;
                padding: 16px;
                font-size: {FONT_BASE + 1}pt;
            }}
            QTabWidget::pane {{
                border: none;
            }}
            QTabBar::tab {{
                background-color: {BG_SURFACE};
                color: {FG_SECONDARY};
                padding: 4px 16px;
                border: none;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: {FG_PRIMARY};
                border-bottom: 2px solid {ACCENT};
            }}
            QTabBar::tab:hover {{
                color: {FG_PRIMARY};
            }}
        """)
