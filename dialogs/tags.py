"""Tag manager dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QKeyEvent

import database as db


class TagManagerDialog(QDialog):
    def __init__(self, parent: QWidget, note_id: int) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gestione Tag")
        self.note_id: int = note_id
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

        self.tag_vars: dict[int, QCheckBox] = {}
        self._load_tags()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Chiudi")
        close_btn.clicked.connect(self._on_close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.exec()

    def _load_tags(self) -> None:
        while self.check_layout.count():
            child = self.check_layout.takeAt(0)
            if child is not None and child.widget():
                child.widget().deleteLater()  # type: ignore[union-attr]

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

    def _add_tag(self) -> None:
        name = self.new_tag_entry.text().strip()
        if name:
            db.add_tag(name)
            self.new_tag_entry.clear()
            self._load_tags()

    def _on_close(self) -> None:
        selected_ids = [tid for tid, cb in self.tag_vars.items() if cb.isChecked()]
        db.set_note_tags(self.note_id, selected_ids)
        self.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._on_close()
        else:
            super().keyPressEvent(event)


class BulkTagDialog(QDialog):
    """Assign/remove tags on multiple notes at once.

    Checkboxes use tri-state: checked = add to all, unchecked = remove from all,
    partial = leave unchanged (initial state when some notes have the tag).
    """

    def __init__(self, parent: QWidget, note_ids: list[int]) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Tag per {len(note_ids)} note")
        self.note_ids: list[int] = note_ids
        self.result: bool = False  # type: ignore[assignment]
        self.setFixedWidth(380)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Add new tag
        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel("Nuovo tag:"))
        self.new_tag_entry = QLineEdit()
        add_layout.addWidget(self.new_tag_entry)
        add_btn = QPushButton("Aggiungi")
        add_btn.clicked.connect(self._add_tag)
        add_layout.addWidget(add_btn)
        layout.addLayout(add_layout)

        layout.addWidget(QLabel("Tag (tri-stato: aggiunge / rimuove / lascia):"))

        # Scrollable area for checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(300)
        self.check_widget = QWidget()
        self.check_layout = QVBoxLayout(self.check_widget)
        self.check_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.check_widget)
        layout.addWidget(scroll)

        self.tag_vars: dict[int, QCheckBox] = {}
        self._load_tags()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("Applica")
        ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(ok_btn)
        cancel_btn = QPushButton("Annulla")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.run_dialog()

    def run_dialog(self) -> None:
        super().exec()

    def _load_tags(self) -> None:
        while self.check_layout.count():
            child = self.check_layout.takeAt(0)
            if child is not None and child.widget():
                child.widget().deleteLater()  # type: ignore[union-attr]

        all_tags = db.get_all_tags()

        # Count how many of the selected notes have each tag
        tag_counts: dict[int, int] = {}
        for nid in self.note_ids:
            for t in db.get_note_tags(nid):
                tag_counts[t["id"]] = tag_counts.get(t["id"], 0) + 1

        total = len(self.note_ids)
        self.tag_vars = {}
        for tag in all_tags:
            cb = QCheckBox(tag["name"])
            cb.setTristate(True)
            count = tag_counts.get(tag["id"], 0)
            if count == total:
                cb.setCheckState(Qt.CheckState.Checked)
            elif count > 0:
                cb.setCheckState(Qt.CheckState.PartiallyChecked)
            else:
                cb.setCheckState(Qt.CheckState.Unchecked)
            self.tag_vars[tag["id"]] = cb
            self.check_layout.addWidget(cb)

        if not all_tags:
            self.check_layout.addWidget(QLabel("Nessun tag creato."))

    def _add_tag(self) -> None:
        name = self.new_tag_entry.text().strip()
        if name:
            db.add_tag(name)
            self.new_tag_entry.clear()
            self._load_tags()

    def _on_ok(self) -> None:
        for tid, cb in self.tag_vars.items():
            state = cb.checkState()
            if state == Qt.CheckState.Checked:
                # Add tag to all notes that don't have it
                for nid in self.note_ids:
                    current = {t["id"] for t in db.get_note_tags(nid)}
                    if tid not in current:
                        db.set_note_tags(nid, list(current | {tid}))
            elif state == Qt.CheckState.Unchecked:
                # Remove tag from all notes that have it
                for nid in self.note_ids:
                    current = {t["id"] for t in db.get_note_tags(nid)}
                    if tid in current:
                        db.set_note_tags(nid, list(current - {tid}))
            # PartiallyChecked = leave unchanged
        self.result = True
        self.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_ok()
        else:
            super().keyPressEvent(event)
