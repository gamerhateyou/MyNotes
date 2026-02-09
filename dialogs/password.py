"""Password input dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from PySide6.QtGui import QKeyEvent


class PasswordDialog(QDialog):
    def __init__(self, parent: QWidget, title: str = "Password", confirm: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.result: str | None = None  # type: ignore[assignment]
        self.setFixedWidth(350)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel("Password:"))
        self.pw_entry = QLineEdit()
        self.pw_entry.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.pw_entry)
        self.pw_entry.setFocus()

        self.pw_confirm: QLineEdit | None = None
        if confirm:
            layout.addWidget(QLabel("Conferma password:"))
            self.pw_confirm = QLineEdit()
            self.pw_confirm.setEchoMode(QLineEdit.EchoMode.Password)
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

    def _on_ok(self) -> None:
        pw = self.pw_entry.text().strip()
        if not pw:
            QMessageBox.warning(self, "Attenzione", "Inserisci una password.")
            return
        if self.pw_confirm is not None and pw != self.pw_confirm.text().strip():
            QMessageBox.warning(self, "Attenzione", "Le password non coincidono.")
            return
        self.result = pw
        self.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_ok()
        elif event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
