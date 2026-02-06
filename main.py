#!/usr/bin/env python3
"""MyNotes - Gestione note, documenti e appunti con database locale."""

import logging
import tkinter as tk
import database as db
from gui import MyNotesApp


def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    db.init_db()
    root = tk.Tk()
    MyNotesApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
