# Privacy Policy - MyNotes

**Last updated:** 2025-02-09

## What MyNotes does

MyNotes is a desktop note-taking application. All your notes, attachments, and settings are stored **locally on your device** in a SQLite database inside the `data/` folder.

## Google Drive integration

MyNotes offers an **optional** Google Drive backup feature. If you choose to enable it:

- The app requests access **only to files it creates** (`drive.file` scope) — it cannot see or modify any other file on your Drive.
- Backup files are uploaded to a dedicated folder (default: "MyNotes Backup") on **your** Google Drive account.
- No data is sent to any server other than Google's own APIs.
- You can disconnect Google Drive at any time from the Backup settings inside the app.
- You can revoke access at any time from [Google Account Permissions](https://myaccount.google.com/permissions).

## Data collection

MyNotes does **not** collect, transmit, or share any personal data. Specifically:

- No analytics or telemetry
- No user accounts or registration
- No data sent to third-party services (other than Google Drive, if you enable it)
- No cookies or tracking

## Encryption

Notes can be individually encrypted with a password using AES (PBKDF2 key derivation). Backups can optionally be encrypted. Passwords are never stored or transmitted.

## Auto-update

MyNotes checks GitHub Releases for updates. This sends a standard HTTPS request to `api.github.com` — no personal data is included.

## Contact

For questions or concerns, open an issue at: https://github.com/gamerhateyou/MyNotes/issues
