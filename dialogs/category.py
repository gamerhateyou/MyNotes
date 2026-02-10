"""Category and Note creation dialogs."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import database as db

if TYPE_CHECKING:
    from PySide6.QtGui import QKeyEvent


def _get_category_depth(cat_id: int, categories: list[sqlite3.Row]) -> int:
    """Return nesting depth of a category (0 = root)."""
    cat_map = {c["id"]: c for c in categories}
    depth = 0
    current_id: int | None = cat_id
    visited: set[int] = set()
    while current_id is not None and current_id not in visited:
        visited.add(current_id)
        cat = cat_map.get(current_id)
        if cat is None or cat["parent_id"] is None:
            break
        depth += 1
        current_id = cat["parent_id"]
    return depth


def _get_category_display_name(cat_id: int) -> str:
    """Return hierarchical display name like 'Parent > Child'."""
    path = db.get_category_path(cat_id)
    return " > ".join(r["name"] for r in path)


class CategoryDialog(QDialog):
    def __init__(self, parent: QWidget, title: str = "Nuova Categoria", initial_name: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.result: str | None = None  # type: ignore[assignment]
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

    def _on_ok(self) -> None:
        name = self.entry.text().strip()
        if name:
            self.result = name
            self.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_ok()
        elif event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)


class NoteDialog(QDialog):
    def __init__(self, parent: QWidget, categories: list[sqlite3.Row]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nuova Nota")
        self.result: dict[str, Any] | None = None  # type: ignore[assignment]
        self.setFixedWidth(400)
        self.setModal(True)
        self.categories: list[sqlite3.Row] = categories

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel("Titolo:"))
        self.title_entry = QLineEdit()
        layout.addWidget(self.title_entry)

        layout.addWidget(QLabel("Categoria:"))
        self.cat_combo = QComboBox()
        self.cat_combo.addItem("(Nessuna)")
        for c in categories:
            depth = _get_category_depth(c["id"], categories)
            indent = "  " * depth
            display = _get_category_display_name(c["id"]) if depth > 0 else c["name"]
            self.cat_combo.addItem(f"{indent}{display}")
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

    def _on_ok(self) -> None:
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

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_ok()
        elif event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
