"""Dialog windows package — re-exports all dialog classes."""

from dialogs.category import CategoryDialog, NoteDialog
from dialogs.tags import TagManagerDialog
from dialogs.attachments import AttachmentDialog
from dialogs.history import VersionHistoryDialog
from dialogs.password import PasswordDialog
from dialogs.audio import AudioRecordDialog
from dialogs.backup import BackupSettingsDialog, BackupRestoreDialog

__all__ = [
    "CategoryDialog", "NoteDialog", "TagManagerDialog",
    "AttachmentDialog", "VersionHistoryDialog", "PasswordDialog",
    "AudioRecordDialog", "BackupSettingsDialog", "BackupRestoreDialog",
]
