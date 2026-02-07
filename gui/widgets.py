"""Custom widget subclasses for MyNotes (PySide6)."""

import re
from PySide6.QtWidgets import QListWidget, QPlainTextEdit, QAbstractItemView
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QDrag, QTextCursor, QColor, QTextCharFormat

from gui.constants import (FG_PRIMARY, FG_MUTED, INFO, BG_ELEVATED,
                           ACCENT, FG_ON_ACCENT)


class DraggableNoteList(QListWidget):
    """QListWidget that supports drag-out with QMimeData containing note IDs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.MoveAction)

    def startDrag(self, supportedActions):
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
        drag.exec(Qt.MoveAction)


class CategoryList(QListWidget):
    """QListWidget that accepts note drops and emits a signal."""

    notes_dropped = Signal(list, int)  # (note_indices, target_row)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-mynotes-indices"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-mynotes-indices"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasFormat("application/x-mynotes-indices"):
            event.ignore()
            return

        data = event.mimeData().data("application/x-mynotes-indices").data().decode()
        indices = [int(i) for i in data.split(",") if i]

        item = self.itemAt(event.position().toPoint())
        target_row = self.row(item) if item else -1

        self.notes_dropped.emit(indices, target_row)
        event.acceptProposedAction()


class ChecklistEditor(QPlainTextEdit):
    """QPlainTextEdit with click-to-toggle checklist items and audio marker clicks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._app = None  # Set by NoteController for audio marker handling

    def set_app(self, app):
        self._app = app

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            cursor = self.cursorForPosition(event.pos())
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
                        import database as db
                        import platform_utils
                        from PySide6.QtWidgets import QMessageBox
                        filename = audio_match.group(1)
                        path = os.path.join(db.ATTACHMENTS_DIR, filename)
                        if os.path.exists(path):
                            platform_utils.open_file(path)
                        else:
                            QMessageBox.warning(self, "Audio",
                                                f"File non trovato:\n{filename}")
                    event.accept()
                    return

            # Checklist toggle
            if stripped.startswith("[ ]") or stripped.startswith("[x]"):
                offset = len(text) - len(stripped)
                cursor = QTextCursor(block)
                cursor.movePosition(QTextCursor.StartOfBlock)
                cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, offset)
                cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 3)

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
