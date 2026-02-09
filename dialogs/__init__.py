"""Dialog windows package — re-exports all dialog classes."""

from __future__ import annotations

from dialogs.attachments import AttachmentDialog
from dialogs.audio import AudioRecordDialog
from dialogs.backup import BackupRestoreDialog, BackupSettingsDialog
from dialogs.category import CategoryDialog, NoteDialog
from dialogs.history import VersionHistoryDialog
from dialogs.password import PasswordDialog
from dialogs.tags import TagManagerDialog

__all__ = [
    "CategoryDialog",
    "NoteDialog",
    "TagManagerDialog",
    "AttachmentDialog",
    "VersionHistoryDialog",
    "PasswordDialog",
    "AudioRecordDialog",
    "BackupSettingsDialog",
    "BackupRestoreDialog",
]
