#!/usr/bin/env python3
"""MyNotes - Gestione note, documenti e appunti con database locale."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

import database as db


def main():
    # Console handler (DEBUG)
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"
    ))

    # File handler (WARNING+)
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
    db._secure_file(log_path)
    db.init_db()

    from PySide6.QtWidgets import QApplication
    import qdarktheme
    from gui import MyNotesApp

    app = QApplication(sys.argv)
    app.setStyleSheet(qdarktheme.load_stylesheet("dark"))
    window = MyNotesApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
