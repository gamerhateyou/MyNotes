"""Category and Note creation dialogs."""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QLineEdit, QPushButton, QComboBox, QMessageBox)
from PySide6.QtCore import Qt


class CategoryDialog(QDialog):
    def __init__(self, parent, title="Nuova Categoria", initial_name=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.result = None
        self.setFixedWidth(350)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel("Nome categoria:"))
        self.entry = QLineEdit()
        self.entry.setText(initial_name)
        layout.addWidget(self.entry)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(ok_btn)
        cancel_btn = QPushButton("Annulla")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.entry.setFocus()
        self.exec()

    def _on_ok(self):
        name = self.entry.text().strip()
        if name:
            self.result = name
            self.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._on_ok()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)


class NoteDialog(QDialog):
    def __init__(self, parent, categories):
        super().__init__(parent)
        self.setWindowTitle("Nuova Nota")
        self.result = None
        self.setFixedWidth(400)
        self.setModal(True)
        self.categories = categories

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel("Titolo:"))
        self.title_entry = QLineEdit()
        layout.addWidget(self.title_entry)

        layout.addWidget(QLabel("Categoria:"))
        self.cat_combo = QComboBox()
        self.cat_combo.addItem("(Nessuna)")
        for c in categories:
            self.cat_combo.addItem(c["name"])
        layout.addWidget(self.cat_combo)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        create_btn = QPushButton("Crea")
        create_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(create_btn)
        cancel_btn = QPushButton("Annulla")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.title_entry.setFocus()
        self.exec()

    def _on_ok(self):
        title = self.title_entry.text().strip()
        if not title:
            QMessageBox.warning(self, "Attenzione", "Inserisci un titolo.")
            return
        cat_id = None
        idx = self.cat_combo.currentIndex()
        if idx > 0:
            cat_id = self.categories[idx - 1]["id"]
        self.result = {"title": title, "category_id": cat_id}
        self.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._on_ok()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
