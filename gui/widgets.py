"""Custom widget subclasses for MyNotes (PySide6)."""

from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import (
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QMouseEvent,
    QTextCursor,
)
from PySide6.QtWidgets import QListWidget, QPlainTextEdit, QTreeWidget, QWidget


class DraggableNoteList(QListWidget):
    """QListWidget that supports drag-out with QMimeData containing note IDs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def startDrag(self, supportedActions: Qt.DropAction) -> None:
        items = self.selectedItems()
        if not items:
            return

        drag = QDrag(self)
        mime = QMimeData()
        # Encode note indices as text (controller resolves to IDs)
        indices = [self.row(item) for item in items]
        mime.setText(",".join(str(i) for i in indices))
        mime.setData("application/x-mynotes-indices", ",".join(str(i) for i in indices).encode())
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)


class CategoryList(QListWidget):
    """QListWidget that accepts note drops and emits a signal."""

    notes_dropped = Signal(list, int)  # (note_indices, target_row)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat("application/x-mynotes-indices"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasFormat("application/x-mynotes-indices"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        if not event.mimeData().hasFormat("application/x-mynotes-indices"):
            event.ignore()
            return

        data = bytes(event.mimeData().data("application/x-mynotes-indices").data()).decode()
        indices = [int(i) for i in data.split(",") if i]

        item = self.itemAt(event.position().toPoint())
        target_row = self.row(item) if item else -1

        self.notes_dropped.emit(indices, target_row)
        event.acceptProposedAction()


class CategoryTree(QTreeWidget):
    """QTreeWidget that accepts note drops and category reparenting via drag-drop."""

    notes_dropped = Signal(list, object)  # (note_indices, QTreeWidgetItem)
    category_dropped = Signal(int, object)  # (cat_id, target QTreeWidgetItem)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(16)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropMode(QTreeWidget.DragDropMode.DragDrop)

    def startDrag(self, supportedActions: Qt.DropAction) -> None:
        item = self.currentItem()
        if not item:
            return
        role_data = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(role_data, int):
            return  # Don't drag special items
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-mynotes-category", str(role_data).encode())
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mime = event.mimeData()
        if mime.hasFormat("application/x-mynotes-indices") or mime.hasFormat("application/x-mynotes-category"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        mime = event.mimeData()
        if mime.hasFormat("application/x-mynotes-indices") or mime.hasFormat("application/x-mynotes-category"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        mime = event.mimeData()
        target_item = self.itemAt(event.position().toPoint())

        if mime.hasFormat("application/x-mynotes-indices"):
            data = bytes(mime.data("application/x-mynotes-indices").data()).decode()
            indices = [int(i) for i in data.split(",") if i]
            self.notes_dropped.emit(indices, target_item)
            event.acceptProposedAction()
        elif mime.hasFormat("application/x-mynotes-category"):
            data = bytes(mime.data("application/x-mynotes-category").data()).decode()
            cat_id = int(data)
            self.category_dropped.emit(cat_id, target_item)
            event.acceptProposedAction()
        else:
            event.ignore()


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
