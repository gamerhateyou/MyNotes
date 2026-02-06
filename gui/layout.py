"""Toolbar and main layout construction."""

import tkinter as tk
from tkinter import ttk
from gui.constants import UI_FONT, MONO_FONT


def build_toolbar(app):
    toolbar = ttk.Frame(app.root, style="Toolbar.TFrame", padding=5)
    toolbar.pack(fill=tk.X)

    ttk.Button(toolbar, text="+ Nota", command=lambda: app.notes_ctl.new_note()).pack(side=tk.LEFT, padx=2)
    ttk.Button(toolbar, text="+ Categoria", command=lambda: app.notes_ctl.new_category()).pack(side=tk.LEFT, padx=2)
    ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

    ttk.Button(toolbar, text="Pin", command=lambda: app.notes_ctl.toggle_pin()).pack(side=tk.LEFT, padx=2)
    ttk.Button(toolbar, text="Fav", command=lambda: app.notes_ctl.toggle_favorite()).pack(side=tk.LEFT, padx=2)
    ttk.Button(toolbar, text="Tag", command=lambda: app.notes_ctl.manage_tags()).pack(side=tk.LEFT, padx=2)
    ttk.Button(toolbar, text="Allegati", command=lambda: app.notes_ctl.manage_attachments()).pack(side=tk.LEFT, padx=2)
    ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

    ttk.Button(toolbar, text="Screenshot", command=lambda: app.media_ctl.take_screenshot()).pack(side=tk.LEFT, padx=2)
    ttk.Button(toolbar, text="Immagine", command=lambda: app.media_ctl.insert_image()).pack(side=tk.LEFT, padx=2)
    ttk.Button(toolbar, text="Checklist", command=lambda: app.notes_ctl.insert_checklist()).pack(side=tk.LEFT, padx=2)

    ttk.Label(toolbar, text="  Cerca:").pack(side=tk.LEFT, padx=(15, 5))
    app.search_var = tk.StringVar()
    app.search_var.trace_add("write", lambda *_: app.notes_ctl.on_search())
    ttk.Entry(toolbar, textvariable=app.search_var, width=18).pack(side=tk.LEFT)

    ttk.Label(toolbar, text="  Tag:").pack(side=tk.LEFT, padx=(10, 5))
    app.tag_filter_var = tk.StringVar()
    app.tag_combo = ttk.Combobox(toolbar, textvariable=app.tag_filter_var, state="readonly", width=12)
    app.tag_combo.pack(side=tk.LEFT)
    app.tag_combo.bind("<<ComboboxSelected>>", lambda e: app.notes_ctl.on_tag_filter())


def build_main_layout(app):
    main_pane = ttk.PanedWindow(app.root, orient=tk.HORIZONTAL)
    main_pane.pack(fill=tk.BOTH, expand=True)

    # Sidebar
    app.sidebar = tk.Frame(main_pane, bg="#2b2b2b", width=200)
    main_pane.add(app.sidebar, weight=0)

    tk.Label(app.sidebar, text="CATEGORIE", bg="#2b2b2b", fg="#888888",
             font=(UI_FONT, 9, "bold"), anchor=tk.W, padx=12, pady=8).pack(fill=tk.X)

    app.cat_listbox = tk.Listbox(
        app.sidebar, bg="#2b2b2b", fg="#cccccc", selectbackground="#3d6fa5",
        selectforeground="#ffffff", font=(UI_FONT, 10), borderwidth=0,
        highlightthickness=0, activestyle="none"
    )
    app.cat_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    app.cat_listbox.bind("<<ListboxSelect>>", lambda e: app.notes_ctl.on_category_select())

    # Center - note list
    center = ttk.Frame(main_pane)
    main_pane.add(center, weight=1)

    app.list_header = ttk.Label(center, text="Note", style="Title.TLabel", padding=(10, 8))
    app.list_header.pack(fill=tk.X)

    app.note_listbox = tk.Listbox(
        center, font=(UI_FONT, 10), selectbackground="#4a90d9",
        selectforeground="#ffffff", borderwidth=0, highlightthickness=1,
        highlightcolor="#cccccc"
    )
    app.note_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
    app.note_listbox.bind("<<ListboxSelect>>", lambda e: app.notes_ctl.on_note_select())
    app.note_listbox.bind("<Delete>", lambda e: app.notes_ctl.delete_note())
    app.note_listbox.bind("<Button-3>", lambda e: app.notes_ctl.show_context_menu(e))

    # Right panel - editor
    editor_frame = ttk.Frame(main_pane)
    main_pane.add(editor_frame, weight=3)

    title_frame = ttk.Frame(editor_frame, padding=(10, 8))
    title_frame.pack(fill=tk.X)
    app.title_var = tk.StringVar()
    app.title_entry = ttk.Entry(title_frame, textvariable=app.title_var, font=(UI_FONT, 14, "bold"))
    app.title_entry.pack(fill=tk.X)
    app.title_var.trace_add("write", lambda *_: app.notes_ctl.schedule_save())

    app.meta_label = ttk.Label(editor_frame, text="", style="Meta.TLabel", padding=(12, 0))
    app.meta_label.pack(fill=tk.X)
    app.tags_label = ttk.Label(editor_frame, text="", style="Meta.TLabel", padding=(12, 2))
    app.tags_label.pack(fill=tk.X)

    editor_pane = ttk.PanedWindow(editor_frame, orient=tk.VERTICAL)
    editor_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

    text_frame = ttk.Frame(editor_pane)
    editor_pane.add(text_frame, weight=3)
    app.text_editor = tk.Text(
        text_frame, font=(MONO_FONT, 11), wrap=tk.WORD,
        undo=True, borderwidth=1, relief=tk.SOLID, padx=8, pady=8
    )
    scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=app.text_editor.yview)
    app.text_editor.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    app.text_editor.pack(fill=tk.BOTH, expand=True)
    app.text_editor.bind("<KeyRelease>", lambda e: app.notes_ctl.schedule_save())
    app.text_editor.bind("<Button-1>", lambda e: app.notes_ctl.on_text_click(e))

    # Checklist tags
    app.text_editor.tag_configure("checkbox_done", overstrike=True, foreground="#888888")
    app.text_editor.tag_configure("checkbox_open", foreground="#333333")

    # Gallery
    gallery_frame = ttk.Frame(editor_pane)
    editor_pane.add(gallery_frame, weight=1)
    gallery_header = ttk.Frame(gallery_frame)
    gallery_header.pack(fill=tk.X)
    ttk.Label(gallery_header, text="Immagini allegate", style="ImgPanel.TLabel").pack(side=tk.LEFT, padx=5)
    ttk.Button(gallery_header, text="Annota", command=lambda: app.media_ctl.annotate_selected()).pack(side=tk.RIGHT, padx=2)
    ttk.Button(gallery_header, text="Apri", command=lambda: app.media_ctl.open_selected()).pack(side=tk.RIGHT, padx=2)
    ttk.Button(gallery_header, text="Rimuovi", command=lambda: app.media_ctl.remove_selected()).pack(side=tk.RIGHT, padx=2)

    app.gallery_canvas = tk.Canvas(gallery_frame, height=120, bg="#f5f5f5",
                                   highlightthickness=1, highlightbackground="#cccccc")
    gallery_scroll = ttk.Scrollbar(gallery_frame, orient=tk.HORIZONTAL, command=app.gallery_canvas.xview)
    app.gallery_canvas.configure(xscrollcommand=gallery_scroll.set)
    gallery_scroll.pack(side=tk.BOTTOM, fill=tk.X)
    app.gallery_canvas.pack(fill=tk.BOTH, expand=True)
    app.gallery_inner = ttk.Frame(app.gallery_canvas)
    app.gallery_canvas.create_window((0, 0), window=app.gallery_inner, anchor=tk.NW)
    app.gallery_inner.bind("<Configure>",
                           lambda e: app.gallery_canvas.configure(scrollregion=app.gallery_canvas.bbox("all")))
    app.selected_image_index = None
    app.gallery_labels = []

    # Status bar
    app.status_var = tk.StringVar(value="Pronto")
    ttk.Label(app.root, textvariable=app.status_var, relief=tk.SUNKEN,
              anchor=tk.W, padding=(8, 3)).pack(fill=tk.X, side=tk.BOTTOM)
