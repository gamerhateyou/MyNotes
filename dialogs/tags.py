"""Tag manager dialog."""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QLineEdit, QPushButton, QCheckBox, QWidget)
from PySide6.QtCore import Qt
import database as db


class TagManagerDialog(QDialog):
    def __init__(self, parent, note_id):
        super().__init__(parent)
        self.setWindowTitle("Gestione Tag")
        self.note_id = note_id
        self.setFixedWidth(350)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel("Nuovo tag:"))
        self.new_tag_entry = QLineEdit()
        add_layout.addWidget(self.new_tag_entry)
        add_btn = QPushButton("Aggiungi")
        add_btn.clicked.connect(self._add_tag)
        add_layout.addWidget(add_btn)
        layout.addLayout(add_layout)

        layout.addWidget(QLabel("Tag disponibili:"))
        self.check_widget = QWidget()
        self.check_layout = QVBoxLayout(self.check_widget)
        self.check_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.check_widget)

        self.tag_vars = {}
        self._load_tags()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Chiudi")
        close_btn.clicked.connect(self._on_close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.exec()

    def _load_tags(self):
        while self.check_layout.count():
            child = self.check_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        all_tags = db.get_all_tags()
        note_tags = db.get_note_tags(self.note_id)
        note_tag_ids = {t["id"] for t in note_tags}
        self.tag_vars = {}
        for tag in all_tags:
            cb = QCheckBox(tag["name"])
            cb.setChecked(tag["id"] in note_tag_ids)
            self.tag_vars[tag["id"]] = cb
            self.check_layout.addWidget(cb)
        if not all_tags:
            self.check_layout.addWidget(QLabel("Nessun tag creato."))

    def _add_tag(self):
        name = self.new_tag_entry.text().strip()
        if name:
            db.add_tag(name)
            self.new_tag_entry.clear()
            self._load_tags()

    def _on_close(self):
        selected_ids = [tid for tid, cb in self.tag_vars.items() if cb.isChecked()]
        db.set_note_tags(self.note_id, selected_ids)
        self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._on_close()
        else:
            super().keyPressEvent(event)
