"""Menu bar and keyboard shortcuts."""

import tkinter as tk
from version import VERSION


def build_menu(app):
    menubar = tk.Menu(app.root)
    app.root.config(menu=menubar)

    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(label="Nuova Nota", command=lambda: app.notes_ctl.new_note(), accelerator="Ctrl+N")
    file_menu.add_command(label="Salva", command=lambda: app.notes_ctl.save_current(), accelerator="Ctrl+S")
    file_menu.add_command(label="Elimina Nota", command=lambda: app.notes_ctl.delete_note(), accelerator="Del")
    file_menu.add_separator()
    file_menu.add_command(label="Esporta nota HTML...", command=lambda: app.export_ctl.export_html(), accelerator="Ctrl+E")
    file_menu.add_command(label="Esporta nota PDF...", command=lambda: app.export_ctl.export_pdf(), accelerator="Ctrl+Shift+E")
    file_menu.add_command(label="Esporta tutte (HTML)...", command=lambda: app.export_ctl.export_all_html())
    file_menu.add_separator()
    file_menu.add_command(label="Condividi nota (.mynote)...", command=lambda: app.export_ctl.export_mynote())
    file_menu.add_command(label="Importa nota (.mynote)...", command=lambda: app.export_ctl.import_mynote())
    file_menu.add_separator()
    file_menu.add_command(label="Esci", command=app._on_close, accelerator="Ctrl+Q")
    menubar.add_cascade(label="File", menu=file_menu)

    cat_menu = tk.Menu(menubar, tearoff=0)
    cat_menu.add_command(label="Nuova Categoria", command=lambda: app.notes_ctl.new_category(), accelerator="Ctrl+Shift+N")
    cat_menu.add_command(label="Rinomina Categoria", command=lambda: app.notes_ctl.rename_category(), accelerator="F2")
    cat_menu.add_command(label="Elimina Categoria", command=lambda: app.notes_ctl.delete_category())
    cat_menu.add_command(label="Svuota Categoria", command=lambda: app.notes_ctl.empty_category())
    menubar.add_cascade(label="Categorie", menu=cat_menu)

    note_menu = tk.Menu(menubar, tearoff=0)
    note_menu.add_command(label="Apri in finestra separata",
                          command=lambda: app.open_in_window(app.current_note_id) if app.current_note_id else None,
                          accelerator="Ctrl+O")
    note_menu.add_separator()
    note_menu.add_command(label="Fissa/Sgancia nota", command=lambda: app.notes_ctl.toggle_pin(), accelerator="Ctrl+P")
    note_menu.add_command(label="Preferita/Non preferita", command=lambda: app.notes_ctl.toggle_favorite(), accelerator="Ctrl+D")
    note_menu.add_separator()
    note_menu.add_command(label="Gestisci Tag", command=lambda: app.notes_ctl.manage_tags(), accelerator="Ctrl+T")
    note_menu.add_command(label="Allegati", command=lambda: app.notes_ctl.manage_attachments())
    note_menu.add_command(label="Cronologia versioni", command=lambda: app.notes_ctl.show_versions(), accelerator="Ctrl+H")
    note_menu.add_separator()
    note_menu.add_command(label="Cripta nota...", command=lambda: app.notes_ctl.encrypt_note())
    note_menu.add_command(label="Decripta nota...", command=lambda: app.notes_ctl.decrypt_note())
    note_menu.add_separator()
    note_menu.add_command(label="Inserisci checklist", command=lambda: app.notes_ctl.insert_checklist(), accelerator="Ctrl+L")
    note_menu.add_separator()
    note_menu.add_command(label="Registra audio...", command=lambda: app.media_ctl.record_audio(), accelerator="Ctrl+Shift+A")
    note_menu.add_command(label="Importa audio...", command=lambda: app.media_ctl.import_audio())
    note_menu.add_separator()
    note_menu.add_command(label="Screenshot intero", command=lambda: app.media_ctl.take_screenshot(), accelerator="Ctrl+Shift+S")
    note_menu.add_command(label="Screenshot regione", command=lambda: app.media_ctl.take_screenshot_region(), accelerator="Ctrl+Shift+R")
    note_menu.add_command(label="Inserisci immagine...", command=lambda: app.media_ctl.insert_image(), accelerator="Ctrl+I")
    menubar.add_cascade(label="Nota", menu=note_menu)

    backup_menu = tk.Menu(menubar, tearoff=0)
    backup_menu.add_command(label="Backup ora", command=lambda: app.backup_ctl.do_backup(), accelerator="Ctrl+B")
    backup_menu.add_command(label="Backup Google Drive", command=lambda: app.backup_ctl.do_gdrive_backup())
    backup_menu.add_separator()
    backup_menu.add_command(label="Ripristina backup...", command=lambda: app.backup_ctl.do_restore())
    backup_menu.add_separator()
    backup_menu.add_command(label="Impostazioni backup...", command=lambda: app.backup_ctl.open_settings())
    menubar.add_cascade(label="Backup", menu=backup_menu)

    help_menu = tk.Menu(menubar, tearoff=0)
    help_menu.add_command(label="Controlla aggiornamenti...", command=lambda: app.update_ctl.check())
    help_menu.add_separator()
    help_menu.add_command(label=f"MyNotes v{VERSION}", state=tk.DISABLED)
    menubar.add_cascade(label="Aiuto", menu=help_menu)

    # Keyboard shortcuts
    app.root.bind("<Control-n>", lambda e: app.notes_ctl.new_note())
    app.root.bind("<Control-q>", lambda e: app._on_close())
    app.root.bind("<Control-p>", lambda e: app.notes_ctl.toggle_pin())
    app.root.bind("<Control-d>", lambda e: app.notes_ctl.toggle_favorite())
    app.root.bind("<Control-l>", lambda e: app.notes_ctl.insert_checklist())
    app.root.bind("<Control-Shift-S>", lambda e: app.media_ctl.take_screenshot())
    app.root.bind("<Control-Shift-R>", lambda e: app.media_ctl.take_screenshot_region())
    app.root.bind("<Control-i>", lambda e: app.media_ctl.insert_image())
    app.root.bind("<Control-Shift-A>", lambda e: app.media_ctl.record_audio())

    # Navigazione e ricerca
    app.root.bind("<Control-f>", lambda e: app.notes_ctl.focus_search())
    app.root.bind("<Escape>", lambda e: app.notes_ctl.clear_search())

    # Salvataggio
    app.root.bind("<Control-s>", lambda e: app.notes_ctl.save_current())

    # Gestione nota
    app.root.bind("<Control-t>", lambda e: app.notes_ctl.manage_tags())
    app.root.bind("<Control-h>", lambda e: app.notes_ctl.show_versions())
    app.root.bind("<Control-e>", lambda e: app.export_ctl.export_html())
    app.root.bind("<Control-Shift-E>", lambda e: app.export_ctl.export_pdf())
    app.root.bind("<Control-o>", lambda e: app.open_in_window(app.current_note_id) if app.current_note_id else None)

    # Categorie
    app.root.bind("<Control-Shift-N>", lambda e: app.notes_ctl.new_category())
    app.root.bind("<F2>", lambda e: app.notes_ctl.rename_category())

    # Backup
    app.root.bind("<Control-b>", lambda e: app.backup_ctl.do_backup())
