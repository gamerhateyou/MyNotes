"""Shared text formatting functions for checklist and audio markers."""

import re
from PySide6.QtGui import QColor, QTextCursor, QTextCharFormat
from gui.constants import FG_PRIMARY, FG_MUTED, INFO, BG_ELEVATED


def apply_checklist_formatting(editor):
    """Apply strikethrough + muted color to [x] lines, normal to [ ] lines."""
    doc = editor.document()
    block = doc.begin()
    while block.isValid():
        text = block.text().strip()
        cursor = QTextCursor(block)
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)

        fmt = QTextCharFormat()
        if text.startswith("[x]"):
            fmt.setFontStrikeOut(True)
            fmt.setForeground(QColor(FG_MUTED))
        elif text.startswith("[ ]"):
            fmt.setFontStrikeOut(False)
            fmt.setForeground(QColor(FG_PRIMARY))
        else:
            fmt.setFontStrikeOut(False)
            fmt.setForeground(QColor(FG_PRIMARY))

        cursor.mergeCharFormat(fmt)
        block = block.next()


_AUDIO_PATTERN = re.compile(r"\[♪:[^\]]+\]")


def apply_audio_formatting(editor):
    """Highlight audio markers [♪:filename desc] with accent color."""
    doc = editor.document()
    block = doc.begin()
    while block.isValid():
        text = block.text()
        for m in _AUDIO_PATTERN.finditer(text):
            cursor = QTextCursor(block)
            cursor.movePosition(QTextCursor.StartOfBlock)
            cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, m.start())
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, m.end() - m.start())
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(INFO))
            fmt.setBackground(QColor(BG_ELEVATED))
            cursor.mergeCharFormat(fmt)
        block = block.next()
