"""MyNotes GUI - Main application controller."""

import logging
import tkinter as tk
from tkinter import ttk
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
        self.root.configure(bg=BG_DARK)

        style = ttk.Style()
        style.theme_use("clam")

        # Base widget styles
        style.configure(".", background=BG_SURFACE, foreground=FG_PRIMARY,
                        bordercolor=BORDER, troughcolor=BG_DARK,
                        fieldbackground=BG_ELEVATED, font=(UI_FONT, FONT_BASE))
        style.map(".", background=[("active", BG_ELEVATED)],
                  foreground=[("disabled", FG_MUTED)])

        # Frames
        style.configure("TFrame", background=BG_SURFACE)
        style.configure("Toolbar.TFrame", background=BG_SURFACE)

        # Labels
        style.configure("TLabel", background=BG_SURFACE, foreground=FG_PRIMARY)
        style.configure("Title.TLabel", font=(UI_FONT, FONT_XL, "bold"))
        style.configure("Meta.TLabel", font=(UI_FONT, FONT_SM), foreground=FG_SECONDARY)
        style.configure("ImgPanel.TLabel", font=(UI_FONT, FONT_SM), foreground=FG_SECONDARY)
        style.configure("Pin.TLabel", font=(UI_FONT, FONT_BASE), foreground=WARNING)

        # Buttons
        style.configure("TButton", background=BG_ELEVATED, foreground=FG_PRIMARY,
                        bordercolor=BORDER, padding=(8, 4))
        style.map("TButton",
                  background=[("active", BORDER_LIGHT), ("pressed", BORDER)],
                  bordercolor=[("focus", ACCENT)])

        # Entry
        style.configure("TEntry", fieldbackground=BG_ELEVATED, foreground=FG_PRIMARY,
                        insertcolor=FG_PRIMARY, bordercolor=BORDER, padding=4)
        style.map("TEntry", bordercolor=[("focus", ACCENT)],
                  fieldbackground=[("readonly", BG_SURFACE)])

        # Combobox
        style.configure("TCombobox", fieldbackground=BG_ELEVATED, foreground=FG_PRIMARY,
                        background=BG_ELEVATED, bordercolor=BORDER,
                        arrowcolor=FG_SECONDARY, padding=4)
        style.map("TCombobox",
                  fieldbackground=[("readonly", BG_ELEVATED)],
                  foreground=[("readonly", FG_PRIMARY)],
                  bordercolor=[("focus", ACCENT)],
                  selectbackground=[("readonly", SELECT_BG)],
                  selectforeground=[("readonly", SELECT_FG)])
        # Combobox dropdown listbox
        self.root.option_add("*TCombobox*Listbox.background", BG_ELEVATED)
        self.root.option_add("*TCombobox*Listbox.foreground", FG_PRIMARY)
        self.root.option_add("*TCombobox*Listbox.selectBackground", SELECT_BG)
        self.root.option_add("*TCombobox*Listbox.selectForeground", SELECT_FG)

        # Scrollbar
        style.configure("Vertical.TScrollbar", background=BORDER,
                        troughcolor=BG_DARK, bordercolor=BG_DARK,
                        arrowcolor=FG_SECONDARY)
        style.configure("Horizontal.TScrollbar", background=BORDER,
                        troughcolor=BG_DARK, bordercolor=BG_DARK,
                        arrowcolor=FG_SECONDARY)

        # PanedWindow
        style.configure("TPanedwindow", background=BG_SURFACE)
        style.configure("Sash", sashthickness=4, gripcount=0,
                        background=BORDER_LIGHT)

        # Checkbutton / Radiobutton
        style.configure("TCheckbutton", background=BG_SURFACE, foreground=FG_PRIMARY,
                        indicatorcolor=BG_ELEVATED, indicatorbackground=BG_ELEVATED)
        style.map("TCheckbutton",
                  indicatorcolor=[("selected", ACCENT)],
                  background=[("active", BG_SURFACE)])
        style.configure("TRadiobutton", background=BG_SURFACE, foreground=FG_PRIMARY)
        style.map("TRadiobutton", background=[("active", BG_SURFACE)])

        # Separator
        style.configure("TSeparator", background=BORDER)

        # LabelFrame
        style.configure("TLabelframe", background=BG_SURFACE, foreground=FG_SECONDARY,
                        bordercolor=BORDER)
        style.configure("TLabelframe.Label", background=BG_SURFACE, foreground=FG_SECONDARY)

        # Spinbox
        style.configure("TSpinbox", fieldbackground=BG_ELEVATED, foreground=FG_PRIMARY,
                        bordercolor=BORDER, arrowcolor=FG_SECONDARY)

        # Progressbar
        style.configure("TProgressbar", troughcolor=BG_DARK, background=ACCENT,
                        bordercolor=BORDER)

        # Menubutton
        style.configure("TMenubutton", background=BG_ELEVATED, foreground=FG_PRIMARY,
                        bordercolor=BORDER, padding=(8, 4))
        style.map("TMenubutton",
                  background=[("active", BORDER_LIGHT)])
