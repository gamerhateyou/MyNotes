"""Pastebin share, manage, settings (PySide6)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

import database as db
import pastebin_utils
from dialogs import PastebinManageDialog, PastebinSettingsDialog, PastebinShareDialog

if TYPE_CHECKING:
    from gui import MyNotesApp

log: logging.Logger = logging.getLogger("pastebin")


class PastebinController:
    def __init__(self, app: MyNotesApp) -> None:
        self.app = app

    def share_note(self) -> None:
        app = self.app
        if app.current_note_id is None:
            QMessageBox.information(app, "Info", "Seleziona una nota prima.")
            return
        note = db.get_note(app.current_note_id)
        if not note:
            return
        if note["is_encrypted"]:
            QMessageBox.warning(app, "Errore", "Non e' possibile condividere una nota criptata.")
            return
        if not pastebin_utils.is_configured():
            QMessageBox.warning(
                app,
                "Pastebin non configurato",
                "Configura la API key nelle impostazioni Pastebin.\nMenu: Condividi > Impostazioni Pastebin...",
            )
            return

        # Salva prima di condividere
        app.notes_ctl.save_current()
        note = db.get_note(app.current_note_id)
        if not note:
            return

        content = note["content"] or ""
        dlg = PastebinShareDialog(app, note["title"], content)
        if not dlg.result:
            return

        params: dict[str, Any] = {
            "note_id": app.current_note_id,
            "content": content,
            **dlg.result,
        }

        # Chiamata sincrona con cursore di attesa
        app.statusBar().showMessage("Pubblicazione su Pastebin in corso...")
        app.setCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            success, result = pastebin_utils.create_paste(
                content=params["content"],
                title=params["title"],
                visibility=params["visibility"],
                expire_date=params["expire_date"],
            )
        except Exception as exc:
            success = False
            result = str(exc)
            log.warning("Errore pastebin: %s", result)
        finally:
            app.unsetCursor()

        if success:
            # Salva nel DB locale
            try:
                paste_key = pastebin_utils.extract_paste_key(result)
                db.add_pastebin_share(
                    note_id=params["note_id"],
                    paste_key=paste_key,
                    paste_url=result,
                    paste_title=params["title"],
                    visibility=params["visibility"],
                    expire_date=params["expire_date"],
                )
            except Exception as exc:
                log.warning("Salvataggio paste nel DB fallito: %s", exc)

            clipboard = QApplication.clipboard()
            assert clipboard is not None
            clipboard.setText(result)
            app.statusBar().showMessage(f"Disponibile a: {result}")
            QMessageBox.information(
                app,
                "Pubblicato",
                f"Nota pubblicata su Pastebin!\n\nDisponibile a:\n{result}\n\n(Link copiato negli appunti)",
            )
            log.info("Paste creato: %s", result)
        else:
            app.statusBar().showMessage("Pubblicazione Pastebin fallita")
            QMessageBox.critical(app, "Errore Pastebin", f"Pubblicazione fallita:\n{result}")
            log.warning("Paste fallito: %s", result)

    def manage_pastes(self) -> None:
        PastebinManageDialog(self.app)

    def open_settings(self) -> None:
        PastebinSettingsDialog(self.app)
