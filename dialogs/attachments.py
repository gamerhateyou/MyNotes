"""Attachment manager dialog."""

import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                                QListWidget, QMessageBox, QFileDialog)

import database as db
import platform_utils


class AttachmentDialog(QDialog):
    def __init__(self, parent, note_id):
        super().__init__(parent)
        self.setWindowTitle("Allegati")
        self.note_id = note_id
        self.resize(450, 350)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        toolbar = QHBoxLayout()
        add_btn = QPushButton("Aggiungi file...")
        add_btn.clicked.connect(self._add_file)
        toolbar.addWidget(add_btn)
        remove_btn = QPushButton("Rimuovi selezionato")
        remove_btn.clicked.connect(self._remove_file)
        toolbar.addWidget(remove_btn)
        open_btn = QPushButton("Apri file")
        open_btn.clicked.connect(self._open_file)
        toolbar.addWidget(open_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.listbox = QListWidget()
        layout.addWidget(self.listbox)

        self.attachments = []
        self._load_attachments()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Chiudi")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.exec()

    def _load_attachments(self):
        self.listbox.clear()
        self.attachments = db.get_note_attachments(self.note_id)
        for att in self.attachments:
            self.listbox.addItem(f"{att['original_name']}  ({att['added_at'][:10]})")

    def _add_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona file da allegare")
        if path:
            db.add_attachment(self.note_id, path)
            self._load_attachments()

    def _remove_file(self):
        row = self.listbox.currentRow()
        if row < 0:
            return
        att = self.attachments[row]
        if QMessageBox.question(
            self, "Conferma",
            f"Rimuovere '{att['original_name']}'?"
        ) == QMessageBox.Yes:
            db.delete_attachment(att["id"])
            self._load_attachments()

    def _open_file(self):
        row = self.listbox.currentRow()
        if row < 0:
            return
        att = self.attachments[row]
        path = os.path.join(db.ATTACHMENTS_DIR, att["filename"])
        if not platform_utils.open_file(path):
            QMessageBox.critical(self, "Errore", "Impossibile aprire il file.")
