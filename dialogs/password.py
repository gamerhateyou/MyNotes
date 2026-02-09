"""Password input dialog."""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QLineEdit, QPushButton, QMessageBox)
from PySide6.QtCore import Qt


class PasswordDialog(QDialog):
    def __init__(self, parent, title="Password", confirm=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.result = None
        self.setFixedWidth(350)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel("Password:"))
        self.pw_entry = QLineEdit()
        self.pw_entry.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.pw_entry)
        self.pw_entry.setFocus()

        self.pw_confirm = None
        if confirm:
            layout.addWidget(QLabel("Conferma password:"))
            self.pw_confirm = QLineEdit()
            self.pw_confirm.setEchoMode(QLineEdit.Password)
            layout.addWidget(self.pw_confirm)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(ok_btn)
        cancel_btn = QPushButton("Annulla")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.exec()

    def _on_ok(self):
        pw = self.pw_entry.text().strip()
        if not pw:
            QMessageBox.warning(self, "Attenzione", "Inserisci una password.")
            return
        if self.pw_confirm is not None:
            if pw != self.pw_confirm.text().strip():
                QMessageBox.warning(self, "Attenzione", "Le password non coincidono.")
                return
        self.result = pw
        self.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._on_ok()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
