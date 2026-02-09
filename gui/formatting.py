"""Shared text formatting functions for checklist and audio markers."""

from __future__ import annotations

import re

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit

from gui.constants import BG_ELEVATED, FG_MUTED, FG_PRIMARY, INFO


def apply_checklist_formatting(editor: QPlainTextEdit) -> None:
    """Apply strikethrough + muted color to [x] lines, normal to [ ] lines."""
    doc = editor.document()
    block = doc.begin()
    while block.isValid():
        text = block.text().strip()
        cursor = QTextCursor(block)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)

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


_AUDIO_PATTERN: re.Pattern[str] = re.compile(r"\[♪:[^\]]+\]")


def apply_audio_formatting(editor: QPlainTextEdit) -> None:
    """Highlight audio markers [♪:filename desc] with accent color."""
    doc = editor.document()
    block = doc.begin()
    while block.isValid():
        text = block.text()
        for m in _AUDIO_PATTERN.finditer(text):
            cursor = QTextCursor(block)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, m.start())
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, m.end() - m.start())
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(INFO))
            fmt.setBackground(QColor(BG_ELEVATED))
            cursor.mergeCharFormat(fmt)
        block = block.next()
