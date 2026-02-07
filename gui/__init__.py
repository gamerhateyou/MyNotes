"""MyNotes GUI - Main application controller."""

import logging
import tkinter as tk
from tkinter import ttk
import database as db
import backup_utils
from version import VERSION

from gui.constants import UI_FONT
from gui.menu import build_menu
from gui.layout import build_toolbar, build_main_layout
from gui.note_controller import NoteController
from gui.export_controller import ExportController
from gui.media_controller import MediaController
from gui.backup_controller import BackupController
from gui.update_controller import UpdateController

log = logging.getLogger("app")


class MyNotesApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"MyNotes v{VERSION}")
        self.root.geometry("1200x750")
        self.root.minsize(900, 550)

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

        # Build UI
        self._setup_styles()
        build_menu(self)
        build_toolbar(self)
        build_main_layout(self)

        # Controllers
        self.notes_ctl = NoteController(self)
        self.export_ctl = ExportController(self)
        self.media_ctl = MediaController(self)
        self.backup_ctl = BackupController(self)
        self.update_ctl = UpdateController(self)

        # Backup scheduler
        self._backup_scheduler = backup_utils.BackupScheduler(self.root)
        self._backup_scheduler.start()

        # Load data
        self.notes_ctl.load_categories()
        self.notes_ctl.load_notes()

        self.root.after(2000, self.update_ctl.check_silent)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def open_in_window(self, note_id):
        if note_id is None:
            return
        if note_id in self._detached_windows:
            win = self._detached_windows[note_id]
            win.lift()
            win.focus_force()
            return
        self.notes_ctl.save_current()
        if self.current_note_id == note_id:
            self.notes_ctl._clear_editor()
        from gui.note_window import NoteWindow
        win = NoteWindow(self, note_id)
        self._detached_windows[note_id] = win

    def _on_close(self):
        for win in list(self._detached_windows.values()):
            win._on_close()
        self.notes_ctl.save_current()
        self._backup_scheduler.stop()
        settings = backup_utils.get_settings()
        if settings.get("auto_backup", True):
            try:
                backup_utils.do_local_backup()
            except Exception as e:
                log.warning("Auto-backup alla chiusura fallito: %s", e)
        self.root.quit()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Toolbar.TFrame", background="#e0e0e0")
        style.configure("Title.TLabel", font=(UI_FONT, 13, "bold"))
        style.configure("Meta.TLabel", font=(UI_FONT, 9), foreground="#666666")
        style.configure("ImgPanel.TLabel", font=(UI_FONT, 9), foreground="#888888")
        style.configure("Pin.TLabel", font=(UI_FONT, 10), foreground="#e6a817")
