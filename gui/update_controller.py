"""Auto-update from GitHub Releases (PySide6)."""

import logging
import threading
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QProgressBar, QPlainTextEdit,
                                QGroupBox, QMessageBox)
from PySide6.QtCore import Qt, QObject, Signal, Slot
from PySide6.QtGui import QFont
import updater
from version import VERSION
from gui.constants import UI_FONT, FG_SECONDARY
from error_codes import AppError

log = logging.getLogger("updater.gui")


class _ThreadSignals(QObject):
    """Signals for thread-safe UI updates."""
    progress = Signal(int, str)
    finished = Signal(bool)
    result_ready = Signal(object)
    error_ready = Signal(object, str, str)


class UpdateController:
    def __init__(self, app):
        self.app = app

    def check_silent(self):
        settings = updater.get_update_settings()
        if not settings.get("auto_check", True):
            log.info("check_silent: auto_check disabilitato, skip")
            return

        skip = settings.get("skipped_versions", [])
        signals = _ThreadSignals(self.app)
        signals.result_ready.connect(lambda r: self._on_silent_result(r))

        def _check():
            try:
                result = updater.check_for_updates(skip_versions=skip)
            except Exception:
                log.warning("check_silent: errore ignorato", exc_info=True)
                return
            if result:
                signals.result_ready.emit(result)

        threading.Thread(target=_check, daemon=True).start()

    def _on_silent_result(self, result):
        tag, url, notes = result
        self._show_update_available(tag, url, notes)

    def check(self):
        log.info("check() avviato dall'utente")
        self.app.statusBar().showMessage("Controllo aggiornamenti...")

        settings = updater.get_update_settings()
        if not settings.get("auto_check", True) or settings.get("skipped_versions"):
            settings["auto_check"] = True
            settings["skipped_versions"] = []
            updater.save_update_settings(settings)
            log.info("check(): riabilitato auto_check e pulito skipped_versions")

        signals = _ThreadSignals(self.app)
        signals.result_ready.connect(lambda r: self._handle_result(r))
        signals.error_ready.connect(lambda c, m, d: self._handle_error(c, m, d))

        def _check():
            try:
                result = updater.check_for_updates()
                log.info("check_for_updates() ritornato: %s", result)
                signals.result_ready.emit(result)
            except AppError as e:
                log.warning("Errore strutturato nel controllo: %s", e, exc_info=True)
                signals.error_ready.emit(e.code, e.message, e.detail)
            except Exception as e:
                log.error("Eccezione nel thread di controllo: %s: %s",
                          type(e).__name__, e, exc_info=True)
                signals.error_ready.emit(None, str(e), "")

        threading.Thread(target=_check, daemon=True).start()

    def _handle_error(self, code, message, detail):
        log.info("_handle_error: code=%s message=%s detail=%s", code, message, detail)
        if code:
            self.app.statusBar().showMessage(f"Errore: {code}")
            body = f"Impossibile verificare aggiornamenti.\n\nCodice errore: {code}\n{message}"
            if detail:
                body += f"\n\nDettaglio: {detail}"
            body += "\n\nFile di log: data/mynotes.log"
        else:
            self.app.statusBar().showMessage("Errore controllo aggiornamenti")
            body = f"Impossibile verificare aggiornamenti.\n\n{message}"
            body += "\n\nFile di log: data/mynotes.log"
        QMessageBox.critical(self.app, "Errore", body)

    def _handle_result(self, result):
        log.info("_handle_result: %s", result)
        if result is None:
            self.app.statusBar().showMessage("Nessun aggiornamento")
            QMessageBox.information(self.app, "Aggiornamenti",
                                    f"MyNotes v{VERSION} e' aggiornato!")
            return
        tag, url, notes = result
        self._show_update_available(tag, url, notes)

    def _show_update_available(self, tag, url, notes):
        dlg = QDialog(self.app)
        dlg.setWindowTitle("Aggiornamento disponibile")
        dlg.setModal(True)
        dlg.setMinimumWidth(450)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel(f"Nuova versione disponibile: {tag}")
        title_label.setFont(QFont(UI_FONT, 12, QFont.Bold))
        layout.addWidget(title_label)

        ver_label = QLabel(f"Versione attuale: v{VERSION}")
        ver_label.setStyleSheet(f"color: {FG_SECONDARY};")
        layout.addWidget(ver_label)

        if notes:
            group = QGroupBox("Note di rilascio")
            group_layout = QVBoxLayout(group)
            notes_text = QPlainTextEdit()
            notes_text.setPlainText(notes)
            notes_text.setReadOnly(True)
            notes_text.setMaximumHeight(200)
            group_layout.addWidget(notes_text)
            layout.addWidget(group)

        btn_layout = QHBoxLayout()

        update_btn = QPushButton("Aggiorna")
        update_btn.clicked.connect(lambda: (dlg.accept(), self._do_update(url)))
        btn_layout.addWidget(update_btn)

        skip_btn = QPushButton(f"Salta {tag}")
        def on_skip():
            settings = updater.get_update_settings()
            skipped = settings.get("skipped_versions", [])
            if tag not in skipped:
                skipped.append(tag)
            settings["skipped_versions"] = skipped
            updater.save_update_settings(settings)
            log.info("Versione %s aggiunta a skipped_versions", tag)
            self.app.statusBar().showMessage(f"Versione {tag} saltata")
            dlg.reject()
        skip_btn.clicked.connect(on_skip)
        btn_layout.addWidget(skip_btn)

        btn_layout.addStretch()

        disable_btn = QPushButton("Non ricordare")
        def on_disable():
            settings = updater.get_update_settings()
            settings["auto_check"] = False
            updater.save_update_settings(settings)
            log.info("auto_check disabilitato dall'utente")
            self.app.statusBar().showMessage("Notifiche aggiornamenti disabilitate")
            dlg.reject()
        disable_btn.clicked.connect(on_disable)
        btn_layout.addWidget(disable_btn)

        layout.addLayout(btn_layout)
        dlg.exec()

    def _do_update(self, download_url):
        app = self.app

        progress_dlg = QDialog(app)
        progress_dlg.setWindowTitle("Aggiornamento")
        progress_dlg.setFixedSize(400, 100)
        progress_dlg.setModal(True)

        layout = QVBoxLayout(progress_dlg)
        layout.setContentsMargins(20, 20, 20, 20)
        status_label = QLabel("Preparazione...")
        layout.addWidget(status_label)
        progress_bar = QProgressBar()
        progress_bar.setMaximum(100)
        layout.addWidget(progress_bar)
        progress_dlg.show()

        last_error = [None]

        signals = _ThreadSignals(app)
        signals.progress.connect(lambda pct, msg: (
            status_label.setText(msg),
            progress_bar.setValue(max(0, int(pct)))
        ))
        signals.finished.connect(lambda success: self._on_update_finished(
            success, last_error[0], progress_dlg, app))

        def on_progress(pct, msg):
            if pct < 0:
                last_error[0] = msg
            signals.progress.emit(int(pct), msg)

        def do_download():
            success = updater.download_and_apply_update(download_url, on_progress)
            signals.finished.emit(success)

        threading.Thread(target=do_download, daemon=True).start()

    def _on_update_finished(self, success, error_msg, progress_dlg, app):
        progress_dlg.close()
        if success:
            import sys
            is_windows = sys.platform == "win32"
            if is_windows:
                QMessageBox.information(
                    app, "Completato",
                    "Aggiornamento scaricato!\n"
                    "L'app si chiudera' e verra' riavviata automaticamente.")
                app.notes_ctl.save_current()
                app.close()
            else:
                if QMessageBox.question(
                    app, "Completato",
                    "Aggiornamento applicato!\nRiavviare ora?"
                ) == QMessageBox.Yes:
                    import subprocess
                    app.notes_ctl.save_current()
                    subprocess.Popen(updater.get_restart_command())
                    app.close()
        else:
            body = "Aggiornamento fallito."
            if error_msg:
                body += f"\n\n{error_msg}"
            body += "\n\nFile di log: data/mynotes.log"
            QMessageBox.critical(app, "Errore", body)
