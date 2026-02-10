"""Pastebin settings, share, and management dialogs."""

from __future__ import annotations

import threading
import webbrowser
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import pastebin_utils
from gui.constants import DANGER, FG_SECONDARY, FONT_BASE, SUCCESS, UI_FONT, WARNING


class PastebinSettingsDialog(QDialog):
    """Configurazione API key e credenziali Pastebin."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Impostazioni Pastebin")
        self.setMinimumWidth(480)
        self.setModal(True)

        self.settings: dict[str, Any] = pastebin_utils.get_settings()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # --- API Key ---
        key_label = QLabel("API Developer Key")
        key_label.setFont(QFont(UI_FONT, FONT_BASE, QFont.Weight.Bold))
        layout.addWidget(key_label)

        key_layout = QHBoxLayout()
        self.key_entry = QLineEdit(self.settings.get("api_dev_key", ""))
        self.key_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_entry.setPlaceholderText("Inserisci la tua API key di Pastebin")
        key_layout.addWidget(self.key_entry)
        self.toggle_key_btn = QPushButton("Mostra")
        self.toggle_key_btn.setFixedWidth(70)
        self.toggle_key_btn.clicked.connect(self._toggle_key_visibility)
        key_layout.addWidget(self.toggle_key_btn)
        layout.addLayout(key_layout)

        key_note = QLabel("Ottieni la tua API key da pastebin.com/doc_api")
        key_note.setStyleSheet(f"color: {FG_SECONDARY}; font-size: 11px;")
        layout.addWidget(key_note)

        # --- Account (opzionale) ---
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep1)

        account_label = QLabel("Account Pastebin (opzionale)")
        account_label.setFont(QFont(UI_FONT, FONT_BASE, QFont.Weight.Bold))
        layout.addWidget(account_label)

        account_note = QLabel("Necessario per paste privati, lista paste e eliminazione.")
        account_note.setStyleSheet(f"color: {FG_SECONDARY}; font-size: 11px;")
        layout.addWidget(account_note)

        user_layout = QHBoxLayout()
        user_layout.addWidget(QLabel("Username:"))
        self.user_entry = QLineEdit(self.settings.get("username", ""))
        user_layout.addWidget(self.user_entry)
        layout.addLayout(user_layout)

        pw_layout = QHBoxLayout()
        pw_layout.addWidget(QLabel("Password:"))
        self.pw_entry = QLineEdit()
        self.pw_entry.setEchoMode(QLineEdit.EchoMode.Password)
        pw_layout.addWidget(self.pw_entry)
        layout.addLayout(pw_layout)

        verify_layout = QHBoxLayout()
        self.verify_btn = QPushButton("Verifica accesso")
        self.verify_btn.clicked.connect(self._verify_login)
        verify_layout.addWidget(self.verify_btn)
        self.login_status = QLabel("")
        verify_layout.addWidget(self.login_status)
        verify_layout.addStretch()
        layout.addLayout(verify_layout)

        if self.settings.get("api_user_key"):
            self.login_status.setText("Accesso configurato")
            self.login_status.setStyleSheet(f"color: {SUCCESS};")

        # --- Default ---
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep2)

        default_label = QLabel("Default pubblicazione")
        default_label.setFont(QFont(UI_FONT, FONT_BASE, QFont.Weight.Bold))
        layout.addWidget(default_label)

        vis_layout = QHBoxLayout()
        vis_layout.addWidget(QLabel("Visibilita':"))
        self.vis_combo = QComboBox()
        for code, label in pastebin_utils.VISIBILITY_LABELS.items():
            self.vis_combo.addItem(label, code)
        default_vis = self.settings.get("default_visibility", 1)
        self.vis_combo.setCurrentIndex(default_vis)
        vis_layout.addWidget(self.vis_combo)
        vis_layout.addStretch()
        layout.addLayout(vis_layout)

        exp_layout = QHBoxLayout()
        exp_layout.addWidget(QLabel("Scadenza:"))
        self.expire_combo = QComboBox()
        for exp_code, exp_label in pastebin_utils.EXPIRE_OPTIONS.items():
            self.expire_combo.addItem(exp_label, exp_code)
        default_exp = self.settings.get("default_expire", "N")
        expire_keys = list(pastebin_utils.EXPIRE_OPTIONS.keys())
        exp_idx = expire_keys.index(default_exp) if default_exp in expire_keys else 0
        self.expire_combo.setCurrentIndex(exp_idx)
        exp_layout.addWidget(self.expire_combo)
        exp_layout.addStretch()
        layout.addLayout(exp_layout)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton("Salva")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)
        cancel_btn = QPushButton("Annulla")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.exec()

    def _toggle_key_visibility(self) -> None:
        if self.key_entry.echoMode() == QLineEdit.EchoMode.Password:
            self.key_entry.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_key_btn.setText("Nascondi")
        else:
            self.key_entry.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_key_btn.setText("Mostra")

    def _verify_login(self) -> None:
        api_key = self.key_entry.text().strip()
        username = self.user_entry.text().strip()
        password = self.pw_entry.text()
        if not api_key:
            QMessageBox.warning(self, "Errore", "Inserisci prima la API key.")
            return
        if not username or not password:
            QMessageBox.warning(self, "Errore", "Inserisci username e password.")
            return

        self.verify_btn.setEnabled(False)
        self.login_status.setText("Verifica in corso...")
        self.login_status.setStyleSheet(f"color: {FG_SECONDARY};")

        def _do_login() -> None:
            try:
                success, result = pastebin_utils.login(api_key, username, password)
                QTimer.singleShot(0, lambda: self._login_done(success, result))
            except ConnectionError as exc:
                err_msg = str(exc)
                QTimer.singleShot(0, lambda: self._login_done(False, err_msg))

        threading.Thread(target=_do_login, daemon=True).start()

    def _login_done(self, success: bool, result: str) -> None:
        self.verify_btn.setEnabled(True)
        if success:
            self.settings["api_user_key"] = result
            self.login_status.setText("Accesso verificato!")
            self.login_status.setStyleSheet(f"color: {SUCCESS};")
        else:
            self.login_status.setText(f"Errore: {result}")
            self.login_status.setStyleSheet(f"color: {DANGER};")

    def _save(self) -> None:
        self.settings["api_dev_key"] = self.key_entry.text().strip()
        self.settings["username"] = self.user_entry.text().strip()
        self.settings["default_visibility"] = self.vis_combo.currentData()
        self.settings["default_expire"] = self.expire_combo.currentData()
        pastebin_utils.save_settings(self.settings)
        QMessageBox.information(self, "Salvato", "Impostazioni Pastebin salvate.")
        self.accept()


class PastebinShareDialog(QDialog):
    """Dialog di conferma pre-pubblicazione su Pastebin."""

    def __init__(self, parent: QWidget, note_title: str, note_content: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pubblica su Pastebin")
        self.setMinimumWidth(450)
        self.setModal(True)
        self.result: dict[str, Any] | None = None  # type: ignore[assignment]

        settings = pastebin_utils.get_settings()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Titolo
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("Titolo paste:"))
        self.title_entry = QLineEdit(note_title)
        title_layout.addWidget(self.title_entry)
        layout.addLayout(title_layout)

        # Visibilita'
        vis_layout = QHBoxLayout()
        vis_layout.addWidget(QLabel("Visibilita':"))
        self.vis_combo = QComboBox()
        for code, label in pastebin_utils.VISIBILITY_LABELS.items():
            self.vis_combo.addItem(label, code)
        default_vis = settings.get("default_visibility", 1)
        self.vis_combo.setCurrentIndex(default_vis)
        vis_layout.addWidget(self.vis_combo)
        vis_layout.addStretch()
        layout.addLayout(vis_layout)

        # Scadenza
        exp_layout = QHBoxLayout()
        exp_layout.addWidget(QLabel("Scadenza:"))
        self.expire_combo = QComboBox()
        for exp_code, exp_label in pastebin_utils.EXPIRE_OPTIONS.items():
            self.expire_combo.addItem(exp_label, exp_code)
        default_exp = settings.get("default_expire", "N")
        expire_keys = list(pastebin_utils.EXPIRE_OPTIONS.keys())
        exp_idx = expire_keys.index(default_exp) if default_exp in expire_keys else 0
        self.expire_combo.setCurrentIndex(exp_idx)
        exp_layout.addWidget(self.expire_combo)
        exp_layout.addStretch()
        layout.addLayout(exp_layout)

        # Anteprima
        preview_label = QLabel("Anteprima contenuto:")
        layout.addWidget(preview_label)
        preview_text = note_content[:200]
        if len(note_content) > 200:
            preview_text += "..."
        preview = QLabel(preview_text)
        preview.setWordWrap(True)
        preview.setStyleSheet(f"color: {FG_SECONDARY}; padding: 8px; font-size: 11px;")
        layout.addWidget(preview)

        # Warning senza user_key
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet(f"color: {WARNING}; font-size: 11px;")
        self.warning_label.setWordWrap(True)
        layout.addWidget(self.warning_label)
        self._has_user_key = pastebin_utils.has_user_key()
        self.vis_combo.currentIndexChanged.connect(self._update_warning)
        self._update_warning()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        publish_btn = QPushButton("Pubblica")
        publish_btn.clicked.connect(self._publish)
        btn_layout.addWidget(publish_btn)
        cancel_btn = QPushButton("Annulla")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.exec()

    def _update_warning(self) -> None:
        vis = self.vis_combo.currentData()
        if vis == 2 and not self._has_user_key:
            self.warning_label.setText(
                "Attenzione: i paste privati richiedono l'accesso con account Pastebin.\n"
                "Configura username e password nelle Impostazioni Pastebin."
            )
        elif not self._has_user_key:
            self.warning_label.setText(
                "Senza account Pastebin il paste non potra' essere eliminato remotamente.\n"
                "Il link sara' salvato in Condividi > Gestione paste."
            )
        else:
            self.warning_label.setText("")

    def _publish(self) -> None:
        title = self.title_entry.text().strip()
        if not title:
            QMessageBox.warning(self, "Errore", "Inserisci un titolo per il paste.")
            return
        self.result = {
            "title": title,
            "visibility": self.vis_combo.currentData(),
            "expire_date": self.expire_combo.currentData(),
        }
        self.accept()


class PastebinManageDialog(QDialog):
    """Gestione paste pubblicati su Pastebin."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gestione Paste Pastebin")
        self.resize(750, 450)
        self.setModal(True)

        import database as db

        self._db = db

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # Info label
        info_label = QLabel("Tutti i paste pubblicati tramite MyNotes sono elencati qui.")
        info_label.setStyleSheet(f"color: {FG_SECONDARY}; font-size: 11px;")
        layout.addWidget(info_label)

        # Empty state label (shown when no shares)
        self._empty_label = QLabel(
            "Nessun paste pubblicato.\nUsa Condividi > Pubblica su Pastebin per pubblicare una nota."
        )
        self._empty_label.setAlignment(QLabel("").alignment())
        self._empty_label.setStyleSheet(f"color: {FG_SECONDARY}; padding: 40px; font-size: 12px;")
        self._empty_label.setWordWrap(True)
        layout.addWidget(self._empty_label)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Titolo paste", "Nota", "Visibilita'", "Data", "URL"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        assert header is not None
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        # Buttons
        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("Copia link")
        copy_btn.clicked.connect(self._copy_link)
        btn_layout.addWidget(copy_btn)
        open_btn = QPushButton("Apri nel browser")
        open_btn.clicked.connect(self._open_browser)
        btn_layout.addWidget(open_btn)
        btn_layout.addStretch()
        delete_btn = QPushButton("Elimina da Pastebin")
        delete_btn.clicked.connect(self._delete_from_pastebin)
        btn_layout.addWidget(delete_btn)
        remove_btn = QPushButton("Rimuovi dalla lista")
        remove_btn.clicked.connect(self._remove_local)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        close_btn = QPushButton("Chiudi")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self._shares: list[Any] = []
        self._load_shares()

        self.exec()

    def _load_shares(self) -> None:
        self._shares = self._db.get_pastebin_shares()
        has_shares = len(self._shares) > 0
        self._empty_label.setVisible(not has_shares)
        self.table.setVisible(has_shares)
        self.table.setRowCount(len(self._shares))
        for i, share in enumerate(self._shares):
            self.table.setItem(i, 0, QTableWidgetItem(share["paste_title"]))
            self.table.setItem(i, 1, QTableWidgetItem(share["note_title"]))
            vis_label = pastebin_utils.VISIBILITY_LABELS.get(share["visibility"], "?")
            self.table.setItem(i, 2, QTableWidgetItem(vis_label))
            date_str = share["shared_at"][:16].replace("T", " ")
            self.table.setItem(i, 3, QTableWidgetItem(date_str))
            self.table.setItem(i, 4, QTableWidgetItem(share["paste_url"]))

    def _get_selected_row(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Info", "Seleziona un paste dalla lista.")
            return None
        return rows[0].row()

    def _copy_link(self) -> None:
        row = self._get_selected_row()
        if row is None:
            return
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        assert clipboard is not None
        clipboard.setText(self._shares[row]["paste_url"])
        QMessageBox.information(self, "Copiato", "Link copiato negli appunti.")

    def _open_browser(self) -> None:
        row = self._get_selected_row()
        if row is None:
            return
        webbrowser.open(self._shares[row]["paste_url"])

    def _delete_from_pastebin(self) -> None:
        row = self._get_selected_row()
        if row is None:
            return
        if not pastebin_utils.has_user_key():
            QMessageBox.warning(
                self,
                "Errore",
                "Per eliminare paste da Pastebin e' necessario l'accesso con account.\n"
                "Configura nelle Impostazioni Pastebin.",
            )
            return
        share = self._shares[row]
        reply = QMessageBox.question(self, "Conferma", f"Eliminare '{share['paste_title']}' da Pastebin?")
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.setEnabled(False)
        paste_key = pastebin_utils.extract_paste_key(share["paste_url"])
        share_id = share["id"]

        def _do_delete() -> None:
            try:
                success, msg = pastebin_utils.delete_paste(paste_key)
                QTimer.singleShot(0, lambda: self._delete_done(success, msg, share_id))
            except ConnectionError as exc:
                err_msg = str(exc)
                QTimer.singleShot(0, lambda: self._delete_done(False, err_msg, share_id))

        threading.Thread(target=_do_delete, daemon=True).start()

    def _delete_done(self, success: bool, msg: str, share_id: int) -> None:
        self.setEnabled(True)
        if success:
            self._db.delete_pastebin_share(share_id)
            self._load_shares()
            QMessageBox.information(self, "Eliminato", "Paste eliminato da Pastebin.")
        else:
            QMessageBox.warning(self, "Errore", f"Eliminazione fallita: {msg}")

    def _remove_local(self) -> None:
        row = self._get_selected_row()
        if row is None:
            return
        share = self._shares[row]
        reply = QMessageBox.question(
            self,
            "Conferma",
            f"Rimuovere '{share['paste_title']}' dalla lista locale?\nIl paste su Pastebin non verra' eliminato.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._db.delete_pastebin_share(share["id"])
        self._load_shares()
