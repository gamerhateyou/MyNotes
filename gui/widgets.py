"""Custom widget subclasses for MyNotes (PySide6)."""

from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent, QTextCursor
from PySide6.QtWidgets import QListWidget, QPlainTextEdit, QTreeWidget, QWidget


class DraggableNoteList(QListWidget):
    """QListWidget for the note list."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)


class CategoryTree(QTreeWidget):
    """QTreeWidget sidebar for hierarchical categories."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(16)


class ChecklistEditor(QPlainTextEdit):
    """QPlainTextEdit with click-to-toggle checklist items and audio marker clicks."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app: Any = None  # Set by NoteController for audio marker handling

    def set_app(self, app: Any) -> None:
        self._app = app

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            cursor = self.cursorForPosition(pos)
            block = cursor.block()
            text = block.text()
            stripped = text.lstrip()

            # Audio marker click
            audio_match = re.search(r"\[♪:(\S+)", text)
            if audio_match:
                col = cursor.positionInBlock()
                marker_match = re.search(r"\[♪:[^\]]+\]", text)
                if marker_match and marker_match.start() <= col <= marker_match.end():
                    if self._app:
                        import os

                        from PySide6.QtWidgets import QMessageBox

                        import database as db
                        import platform_utils

                        filename = audio_match.group(1)
                        path = os.path.join(db.ATTACHMENTS_DIR, filename)
                        if os.path.exists(path):
                            platform_utils.open_file(path)
                        else:
                            QMessageBox.warning(self, "Audio", f"File non trovato:\n{filename}")
                    event.accept()
                    return

            # Checklist toggle
            if stripped.startswith("[ ]") or stripped.startswith("[x]"):
                offset = len(text) - len(stripped)
                cursor = QTextCursor(block)
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, offset)
                cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 3)

                if stripped.startswith("[ ]"):
                    cursor.insertText("[x]")
                else:
                    cursor.insertText("[ ]")

                # Re-apply formatting
                if self._app:
                    self._app.notes_ctl._apply_checklist_formatting()
                    self._app.notes_ctl.schedule_save()
                event.accept()
                return

        super().mousePressEvent(event)
