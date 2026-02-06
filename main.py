#!/usr/bin/env python3
"""MyNotes - Gestione note, documenti e appunti con database locale."""

import tkinter as tk
import database as db
from gui import MyNotesApp


def main():
    db.init_db()
    root = tk.Tk()
    MyNotesApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
