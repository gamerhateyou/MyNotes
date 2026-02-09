"""Toolbar and main layout construction (PySide6)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from gui.constants import (
    ACCENT,
    BG_SURFACE,
    DANGER,
    FG_MUTED,
    FG_SECONDARY,
    FONT_LG,
    FONT_SM,
    FONT_XL,
    MONO_FONT,
    UI_FONT,
)

if TYPE_CHECKING:
    from gui import MyNotesApp


def build_toolbar(app: MyNotesApp) -> None:
    toolbar = QToolBar("Toolbar")
    toolbar.setMovable(False)
    toolbar.setIconSize(QSize(20, 20))
    app.addToolBar(toolbar)

    style = app.style()
    assert style is not None

    new_note_btn = QPushButton("Nota")
    new_note_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileIcon))
    new_note_btn.clicked.connect(lambda: app.notes_ctl.new_note())
    toolbar.addWidget(new_note_btn)

    new_cat_btn = QPushButton("Categoria")
    new_cat_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirIcon))
    new_cat_btn.clicked.connect(lambda: app.notes_ctl.new_category())
    toolbar.addWidget(new_cat_btn)

    toolbar.addSeparator()

    # Dropdown "Nota"
    note_btn = QPushButton("Nota")
    note_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
    note_menu = QMenu(note_btn)
    note_menu.addAction("Fissa/Sgancia", lambda: app.notes_ctl.toggle_pin())
    note_menu.addAction("Preferita", lambda: app.notes_ctl.toggle_favorite())
    note_menu.addSeparator()
    note_menu.addAction("Tag...", lambda: app.notes_ctl.manage_tags())
    note_menu.addAction("Allegati...", lambda: app.notes_ctl.manage_attachments())
    note_btn.setMenu(note_menu)
    toolbar.addWidget(note_btn)

    # Dropdown "Inserisci"
    ins_btn = QPushButton("Inserisci")
    ins_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
    ins_menu = QMenu(ins_btn)
    ins_menu.addAction("Screenshot intero", lambda: app.media_ctl.take_screenshot())
    ins_menu.addAction("Screenshot regione", lambda: app.media_ctl.take_screenshot_region())
    ins_menu.addAction("Immagine...", lambda: app.media_ctl.insert_image())
    ins_menu.addSeparator()
    ins_menu.addAction("Checklist", lambda: app.notes_ctl.insert_checklist())
    ins_menu.addSeparator()
    ins_menu.addAction("Registra audio...", lambda: app.media_ctl.record_audio())
    ins_menu.addAction("Importa audio...", lambda: app.media_ctl.import_audio())
    ins_btn.setMenu(ins_menu)
    toolbar.addWidget(ins_btn)

    toolbar.addSeparator()

    app.search_entry = QLineEdit()
    app.search_entry.setFixedWidth(180)
    app.search_entry.setPlaceholderText("Cerca note...")
    app.search_entry.textChanged.connect(lambda: app.notes_ctl.on_search())
    toolbar.addWidget(app.search_entry)

    app.tag_combo = QComboBox()
    app.tag_combo.setFixedWidth(140)
    app.tag_combo.currentIndexChanged.connect(lambda: app.notes_ctl.on_tag_filter())
    toolbar.addWidget(app.tag_combo)


def build_main_layout(app: MyNotesApp) -> None:
    central = QWidget()
    app.setCentralWidget(central)
    main_layout = QVBoxLayout(central)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)

    splitter = QSplitter(Qt.Orientation.Horizontal)
    main_layout.addWidget(splitter)

    # --- Sidebar (categories) ---
    sidebar = QWidget()
    sidebar_layout = QVBoxLayout(sidebar)
    sidebar_layout.setContentsMargins(0, 0, 0, 0)
    sidebar_layout.setSpacing(0)

    cat_header = QLabel("CATEGORIE")
    cat_header.setStyleSheet(
        f"background-color: {BG_SURFACE}; color: {FG_SECONDARY}; "
        f"font-size: {FONT_SM}pt; font-weight: bold; padding: 8px 12px;"
    )
    sidebar_layout.addWidget(cat_header)

    from gui.widgets import CategoryList

    app.cat_listbox = CategoryList()
    app.cat_listbox.setStyleSheet(f"background-color: {BG_SURFACE}; border: none;")
    app.cat_listbox.itemClicked.connect(lambda item: app.notes_ctl.on_category_select())
    app.cat_listbox.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    app.cat_listbox.customContextMenuRequested.connect(lambda pos: app.notes_ctl.show_category_context_menu(pos))
    sidebar_layout.addWidget(app.cat_listbox)

    sidebar.setMinimumWidth(160)
    sidebar.setMaximumWidth(300)
    splitter.addWidget(sidebar)

    # --- Center (note list) ---
    center = QWidget()
    center_layout = QVBoxLayout(center)
    center_layout.setContentsMargins(0, 0, 0, 0)
    center_layout.setSpacing(0)

    app.list_header = QLabel("Note")
    app.list_header.setStyleSheet(
        f"font-size: {FONT_XL}pt; font-weight: bold; padding: 8px 10px; background-color: {BG_SURFACE};"
    )
    center_layout.addWidget(app.list_header)

    from gui.widgets import DraggableNoteList

    app.note_listbox = DraggableNoteList()
    app.note_listbox.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    app.note_listbox.itemClicked.connect(lambda item: app.notes_ctl.on_note_click(item))
    app.note_listbox.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    app.note_listbox.customContextMenuRequested.connect(lambda pos: app.notes_ctl.show_context_menu(pos))
    app.note_listbox.itemDoubleClicked.connect(lambda item: app.notes_ctl.on_note_double_click(item))
    center_layout.addWidget(app.note_listbox)

    center.setMinimumWidth(200)
    splitter.addWidget(center)

    # --- Right (editor) ---
    editor_widget = QWidget()
    editor_layout = QVBoxLayout(editor_widget)
    editor_layout.setContentsMargins(10, 6, 10, 10)
    editor_layout.setSpacing(6)

    # Title
    app.title_entry = QLineEdit()
    app.title_entry.setFont(QFont(UI_FONT, FONT_XL, QFont.Weight.Bold))
    app.title_entry.setPlaceholderText("Titolo nota...")
    app.title_entry.setStyleSheet(
        f"border: none; background: transparent; padding: 8px; font-size: {FONT_XL}pt; font-weight: bold;"
    )
    app.title_entry.textChanged.connect(lambda: app.notes_ctl.schedule_save())
    editor_layout.addWidget(app.title_entry)

    # Meta labels
    app.meta_label = QLabel("")
    app.meta_label.setStyleSheet(f"color: {FG_SECONDARY}; font-size: {FONT_SM}pt; padding: 0px 12px;")
    editor_layout.addWidget(app.meta_label)

    app.tags_label = QLabel("")
    app.tags_label.setStyleSheet(f"color: {FG_SECONDARY}; font-size: {FONT_SM}pt; padding: 2px 12px;")
    editor_layout.addWidget(app.tags_label)

    # Editor + gallery vertical splitter
    editor_splitter = QSplitter(Qt.Orientation.Vertical)
    editor_layout.addWidget(editor_splitter)

    # QStackedWidget for editor / decrypt overlay
    app.editor_stack = QStackedWidget()

    # Page 0: text editor
    from gui.widgets import ChecklistEditor

    app.text_editor = ChecklistEditor()
    app.text_editor.setFont(QFont(MONO_FONT, FONT_LG))
    app.text_editor.setPlaceholderText("Scrivi qui...")
    app.text_editor.textChanged.connect(lambda: app.notes_ctl.schedule_save())
    app.editor_stack.addWidget(app.text_editor)

    # Page 1: decrypt overlay
    encrypt_overlay = QWidget()
    overlay_layout = QVBoxLayout(encrypt_overlay)
    overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    lock_label = QLabel("Nota criptata")
    lock_label.setFont(QFont(UI_FONT, FONT_XL))
    lock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lock_label.setStyleSheet(f"color: {FG_SECONDARY};")
    overlay_layout.addWidget(lock_label)

    hint_label = QLabel("Inserisci la password per visualizzare il contenuto")
    hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hint_label.setStyleSheet(f"color: {FG_MUTED};")
    overlay_layout.addWidget(hint_label)

    pw_row = QHBoxLayout()
    pw_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
    app.decrypt_entry = QLineEdit()
    app.decrypt_entry.setEchoMode(QLineEdit.EchoMode.Password)
    app.decrypt_entry.setPlaceholderText("Password...")
    app.decrypt_entry.setFixedWidth(250)
    pw_row.addWidget(app.decrypt_entry)

    app.decrypt_btn = QPushButton("Sblocca")
    pw_row.addWidget(app.decrypt_btn)
    overlay_layout.addLayout(pw_row)

    app.decrypt_error_label = QLabel("")
    app.decrypt_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    app.decrypt_error_label.setStyleSheet(f"color: {DANGER};")
    overlay_layout.addWidget(app.decrypt_error_label)

    app.editor_stack.addWidget(encrypt_overlay)

    editor_splitter.addWidget(app.editor_stack)

    # Gallery area
    gallery_widget = QWidget()
    gallery_layout = QVBoxLayout(gallery_widget)
    gallery_layout.setContentsMargins(0, 0, 0, 0)
    gallery_layout.setSpacing(2)

    gallery_header = QWidget()
    gallery_header_layout = QHBoxLayout(gallery_header)
    gallery_header_layout.setContentsMargins(8, 4, 8, 4)
    gallery_header_layout.setSpacing(4)
    gallery_header_label = QLabel("Immagini allegate")
    gallery_header_label.setStyleSheet(f"color: {FG_SECONDARY}; font-size: {FONT_SM}pt;")
    gallery_header_layout.addWidget(gallery_header_label)
    gallery_header_layout.addStretch()

    style_g = app.style()
    assert style_g is not None

    remove_btn = QPushButton("Rimuovi")
    remove_btn.setIcon(style_g.standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
    remove_btn.clicked.connect(lambda: app.media_ctl.remove_selected())
    gallery_header_layout.addWidget(remove_btn)
    open_btn = QPushButton("Apri")
    open_btn.setIcon(style_g.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
    open_btn.clicked.connect(lambda: app.media_ctl.open_selected())
    gallery_header_layout.addWidget(open_btn)
    annotate_btn = QPushButton("Annota")
    annotate_btn.setIcon(style_g.standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView))
    annotate_btn.clicked.connect(lambda: app.media_ctl.annotate_selected())
    gallery_header_layout.addWidget(annotate_btn)

    gallery_layout.addWidget(gallery_header)

    app.gallery_scroll = QScrollArea()
    app.gallery_scroll.setWidgetResizable(True)
    app.gallery_scroll.setMinimumHeight(100)
    app.gallery_scroll.setMaximumHeight(180)

    app.gallery_inner = QWidget()
    app.gallery_inner_layout = QHBoxLayout(app.gallery_inner)
    app.gallery_inner_layout.setContentsMargins(4, 4, 4, 4)
    app.gallery_inner_layout.setSpacing(6)
    app.gallery_inner_layout.addStretch()
    app.gallery_scroll.setWidget(app.gallery_inner)

    gallery_layout.addWidget(app.gallery_scroll)
    editor_splitter.addWidget(gallery_widget)

    # Splitter proportions (editor 3:1 gallery)
    editor_splitter.setStretchFactor(0, 3)
    editor_splitter.setStretchFactor(1, 1)

    splitter.addWidget(editor_widget)

    # Main splitter proportions
    splitter.setStretchFactor(0, 0)  # sidebar fixed
    splitter.setStretchFactor(1, 1)  # note list
    splitter.setStretchFactor(2, 3)  # editor
    splitter.setSizes([200, 250, 750])

    # Gallery state
    app.selected_image_index = None
    app.gallery_labels = []

    # Status bar
    status_bar = QStatusBar()
    app.setStatusBar(status_bar)
    status_bar.showMessage("Pronto")

    # Branding link (permanent widget, right side)
    brand_label = QLabel(f'<a href="https://homelabz.cc" style="color: {ACCENT};">homelabz.cc</a>')
    brand_label.setOpenExternalLinks(True)
    brand_label.setStyleSheet(f"padding-right: 8px; font-size: {FONT_SM}pt;")
    status_bar.addPermanentWidget(brand_label)
