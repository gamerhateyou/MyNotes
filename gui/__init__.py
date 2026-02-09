"""MyNotes GUI - Main application window (PySide6)."""

import logging
from PySide6.QtWidgets import QMainWindow, QApplication
from PySide6.QtCore import QTimer

import database as db
import backup_utils
from version import VERSION

from gui.constants import (UI_FONT, MONO_FONT, FONT_SM, FONT_BASE, FONT_XL,
                           BG_DARK, BG_SURFACE, BG_ELEVATED,
                           BORDER, BORDER_LIGHT,
                           FG_PRIMARY, FG_SECONDARY, FG_MUTED, FG_ON_ACCENT,
                           ACCENT, WARNING, SELECT_BG, SELECT_FG)
from gui.menu import build_menu
from gui.layout import build_toolbar, build_main_layout
from gui.note_controller import NoteController
from gui.export_controller import ExportController
from gui.media_controller import MediaController
from gui.backup_controller import BackupController
from gui.update_controller import UpdateController

log = logging.getLogger("app")


class MyNotesApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"MyNotes v{VERSION}")
        self.resize(1200, 750)
        self.setMinimumSize(900, 550)

        # State
        self.current_note_id = None
        self.current_category_id = None
        self.current_tag_id = None
        self.show_trash = False
        self.show_favorites = False
        self._save_job = None
        self._image_refs = []
        self._version_counter = 0
        self._decrypted_cache = {}
        self._detached_windows = {}

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

    def open_in_window(self, note_id):
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

    def _check_backup_password(self):
        """Se crittografia backup attiva ma password non in memoria, chiedi all'utente."""
        settings = backup_utils.get_settings()
        if settings.get("encrypt_backups") and not backup_utils.has_backup_password():
            from dialogs.password import PasswordDialog
            dlg = PasswordDialog(self, title="Password backup")
            if dlg.result:
                backup_utils.set_backup_password(dlg.result)
            else:
                self.statusBar().showMessage(
                    "Crittografia backup disattivata (nessuna password)")
                settings["encrypt_backups"] = False
                backup_utils.save_settings(settings)

    def closeEvent(self, event):
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

    def _apply_qss(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {BG_DARK};
            }}
            QListWidget {{
                background-color: {BG_ELEVATED};
                color: {FG_PRIMARY};
                border: 1px solid {BORDER};
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
                width: 4px;
            }}
            QSplitter::handle:vertical {{
                height: 4px;
            }}
            QToolBar {{
                background-color: {BG_SURFACE};
                border-bottom: 1px solid {BORDER};
                spacing: 4px;
                padding: 4px;
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
            }}
            QPushButton {{
                background-color: {BG_ELEVATED};
                color: {FG_PRIMARY};
                border: 1px solid {BORDER};
                padding: 4px 12px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {BORDER_LIGHT};
            }}
            QPushButton:pressed {{
                background-color: {BORDER};
            }}
            QLabel {{
                color: {FG_PRIMARY};
            }}
        """)
