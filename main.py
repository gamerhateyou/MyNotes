#!/usr/bin/env python3
"""MyNotes - Gestione note, documenti e appunti con database locale."""

import logging
import os
from logging.handlers import RotatingFileHandler
import tkinter as tk
import database as db
from gui import MyNotesApp


def main():
    # Console handler (DEBUG) — comportamento invariato
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"
    ))

    # File handler (WARNING+) — log persistente con rotazione
    os.makedirs(db.DATA_DIR, exist_ok=True)
    log_path = os.path.join(db.DATA_DIR, "mynotes.log")
    file_handler = RotatingFileHandler(
        log_path, maxBytes=512 * 1024, backupCount=2, encoding="utf-8"
    )
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    logging.basicConfig(level=logging.DEBUG, handlers=[console, file_handler])
    db.init_db()
    root = tk.Tk()
    MyNotesApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
