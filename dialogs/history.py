"""Version history dialog."""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QListWidget, QPlainTextEdit,
                                QMessageBox)
import database as db


class VersionHistoryDialog(QDialog):
    def __init__(self, parent, note_id):
        super().__init__(parent)
        self.setWindowTitle("Cronologia versioni")
        self.note_id = note_id
        self.result = None
        self.resize(600, 450)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        layout.addWidget(QLabel("Versioni salvate:"))

        self.version_list = QListWidget()
        self.version_list.currentRowChanged.connect(self._on_select)
        layout.addWidget(self.version_list)

        layout.addWidget(QLabel("Anteprima:"))
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(200)
        layout.addWidget(self.preview)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        restore_btn = QPushButton("Ripristina questa versione")
        restore_btn.clicked.connect(self._restore)
        btn_layout.addWidget(restore_btn)
        close_btn = QPushButton("Chiudi")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.versions = db.get_note_versions(note_id)
        for v in self.versions:
            date = v["saved_at"][:19].replace("T", " ")
            title = v["title"][:40]
            self.version_list.addItem(f"[{date}]  {title}")

        if not self.versions:
            self.version_list.addItem("Nessuna versione precedente salvata.")

        self.exec()

    def _on_select(self, row):
        if row < 0 or not self.versions:
            return
        ver = self.versions[row]
        self.preview.setPlainText(ver["content"] or "")

    def _restore(self):
        row = self.version_list.currentRow()
        if row < 0 or not self.versions:
            return
        ver = self.versions[row]
        if QMessageBox.question(
            self, "Ripristina",
            "Ripristinare questa versione?\nLa versione attuale verra' salvata."
        ) == QMessageBox.Yes:
            note = db.get_note(self.note_id)
            if note:
                db.save_version(self.note_id, note["title"], note["content"])
            db.restore_version(self.note_id, ver["id"])
            self.result = True
            self.accept()
