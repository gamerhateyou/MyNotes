"""Shared type aliases for MyNotes."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

# Database row types — sqlite3.Row supports dict-like access
type NoteRow = sqlite3.Row
type CategoryRow = sqlite3.Row
type TagRow = sqlite3.Row
type AttachmentRow = sqlite3.Row
type VersionRow = sqlite3.Row

# Callback types
type ProgressCallback = Callable[[int, str], None]
type GDriveCallback = Callable[[bool, str], None]
