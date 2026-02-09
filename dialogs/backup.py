"""Backup settings and restore dialogs."""

from __future__ import annotations

import os
import threading
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import database as db
from dialogs.password import PasswordDialog
from gui.constants import DANGER, FG_SECONDARY, FONT_BASE, SUCCESS, UI_FONT


class BackupSettingsDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Impostazioni Backup")
        self.setMinimumWidth(500)
        self.setModal(True)

        import backup_utils

        self.backup_utils: Any = backup_utils
        self.settings: dict[str, Any] = backup_utils.get_settings()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # --- Local Backup ---
        local_label = QLabel("Backup Locale")
        local_label.setFont(QFont(UI_FONT, FONT_BASE, QFont.Weight.Bold))
        layout.addWidget(local_label)

        self.auto_cb = QCheckBox("Backup automatico alla chiusura")
        self.auto_cb.setChecked(self.settings.get("auto_backup", True))
        layout.addWidget(self.auto_cb)

        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Cartella backup locale:"))
        self.dir_entry = QLineEdit(self.settings.get("local_backup_dir", ""))
        dir_layout.addWidget(self.dir_entry)
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self._browse_dir)
        dir_layout.addWidget(browse_btn)
        layout.addLayout(dir_layout)

        max_layout = QHBoxLayout()
        max_layout.addWidget(QLabel("Max backup locali:"))
        self.max_spin = QSpinBox()
        self.max_spin.setRange(1, 100)
        self.max_spin.setValue(self.settings.get("max_local_backups", 10))
        max_layout.addWidget(self.max_spin)
        max_layout.addStretch()
        layout.addLayout(max_layout)

        ret_layout = QHBoxLayout()
        ret_layout.addWidget(QLabel("Cancella backup piu vecchi di (giorni):"))
        self.retention_spin = QSpinBox()
        self.retention_spin.setRange(0, 365)
        self.retention_spin.setValue(self.settings.get("retention_days", 90))
        ret_layout.addWidget(self.retention_spin)
        ret_layout.addWidget(QLabel("0 = mai"))
        ret_layout.addStretch()
        layout.addLayout(ret_layout)

        # --- Google Drive ---
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep1)

        gdrive_label = QLabel("Google Drive")
        gdrive_label.setFont(QFont(UI_FONT, FONT_BASE, QFont.Weight.Bold))
        layout.addWidget(gdrive_label)

        status_layout = QHBoxLayout()
        self.gdrive_status_label = QLabel("")
        status_layout.addWidget(self.gdrive_status_label)
        status_layout.addStretch()
        self.auth_btn = QPushButton("")
        self.auth_btn.clicked.connect(self._toggle_gdrive_auth)
        status_layout.addWidget(self.auth_btn)
        layout.addLayout(status_layout)
        self._update_gdrive_status()

        self.gdrive_cb = QCheckBox("Abilita backup su Google Drive")
        self.gdrive_cb.setChecked(self.settings.get("gdrive_enabled", False))
        layout.addWidget(self.gdrive_cb)

        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel("Nome cartella su Drive:"))
        self.folder_entry = QLineEdit(self.settings.get("gdrive_folder_name", "MyNotes Backup"))
        folder_layout.addWidget(self.folder_entry)
        layout.addLayout(folder_layout)

        gdrive_max_layout = QHBoxLayout()
        gdrive_max_layout.addWidget(QLabel("Max backup su Drive:"))
        self.gdrive_max_spin = QSpinBox()
        self.gdrive_max_spin.setRange(0, 100)
        self.gdrive_max_spin.setValue(self.settings.get("max_gdrive_backups", 20))
        gdrive_max_layout.addWidget(self.gdrive_max_spin)
        gdrive_max_layout.addWidget(QLabel("0 = illimitato"))
        gdrive_max_layout.addStretch()
        layout.addLayout(gdrive_max_layout)

        # --- Crittografia ---
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep2)

        enc_label = QLabel("Crittografia")
        enc_label.setFont(QFont(UI_FONT, FONT_BASE, QFont.Weight.Bold))
        layout.addWidget(enc_label)

        self.encrypt_cb = QCheckBox("Cripta backup con password")
        self.encrypt_cb.setChecked(self.settings.get("encrypt_backups", False))
        layout.addWidget(self.encrypt_cb)

        pw_set = backup_utils.has_backup_password()
        pw_status = "Password in memoria" if pw_set else "Password non impostata"
        pw_color = SUCCESS if pw_set else FG_SECONDARY
        self.pw_status_label = QLabel(pw_status)
        self.pw_status_label.setStyleSheet(f"color: {pw_color};")
        layout.addWidget(self.pw_status_label)

        pw_note = QLabel("La password non viene salvata su disco.\nViene chiesta all'avvio dell'app.")
        pw_note.setStyleSheet(f"color: {FG_SECONDARY}; font-size: 11px;")
        layout.addWidget(pw_note)

        # --- Scheduler ---
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep3)

        sched_label = QLabel("Backup Automatico")
        sched_label.setFont(QFont(UI_FONT, FONT_BASE, QFont.Weight.Bold))
        layout.addWidget(sched_label)

        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Intervallo backup:"))
        self._interval_labels = ["Disabilitato", "30 minuti", "1 ora", "2 ore", "4 ore", "8 ore", "12 ore", "24 ore"]
        self._interval_values = [0, 30, 60, 120, 240, 480, 720, 1440]
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(self._interval_labels)
        current_interval = self.settings.get("backup_interval_minutes", 0)
        idx = self._interval_values.index(current_interval) if current_interval in self._interval_values else 0
        self.interval_combo.setCurrentIndex(idx)
        interval_layout.addWidget(self.interval_combo)
        interval_layout.addStretch()
        layout.addLayout(interval_layout)

        last_backup = self.settings.get("last_backup_time", "")
        last_text = f"Ultimo backup: {last_backup}" if last_backup else "Ultimo backup: mai"
        last_label = QLabel(last_text)
        last_label.setStyleSheet(f"color: {FG_SECONDARY};")
        layout.addWidget(last_label)

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

    def _update_gdrive_status(self) -> None:
        if self.backup_utils.is_gdrive_configured():
            self.gdrive_status_label.setText("Connesso a Google Drive")
            self.gdrive_status_label.setStyleSheet(f"color: {SUCCESS};")
            self.auth_btn.setText("Disconnetti")
        else:
            self.gdrive_status_label.setText("Non connesso")
            self.gdrive_status_label.setStyleSheet(f"color: {FG_SECONDARY};")
            self.auth_btn.setText("Accedi con Google")

    def _toggle_gdrive_auth(self) -> None:
        if self.backup_utils.is_gdrive_configured():
            answer = QMessageBox.question(self, "Disconnetti", "Rimuovere l'autorizzazione Google Drive?")
            if answer == QMessageBox.StandardButton.Yes:
                self.backup_utils.gdrive_disconnect()
                self.gdrive_cb.setChecked(False)
                self._update_gdrive_status()
        else:
            self.auth_btn.setEnabled(False)
            self.auth_btn.setText("Autorizzazione in corso...")

            def _do_auth() -> None:
                success, msg = self.backup_utils.gdrive_authorize()
                QTimer.singleShot(0, lambda: self._auth_done(success, msg))

            threading.Thread(target=_do_auth, daemon=True).start()

    def _auth_done(self, success: bool, msg: str) -> None:
        self.auth_btn.setEnabled(True)
        if success:
            QMessageBox.information(self, "Google Drive", msg)
        else:
            QMessageBox.critical(self, "Errore", msg)
        self._update_gdrive_status()

    def _browse_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Cartella backup")
        if d:
            self.dir_entry.setText(d)

    def _save(self) -> None:
        self.settings["auto_backup"] = self.auto_cb.isChecked()
        self.settings["local_backup_dir"] = self.dir_entry.text()
        self.settings["max_local_backups"] = self.max_spin.value()
        self.settings["retention_days"] = self.retention_spin.value()
        self.settings["gdrive_enabled"] = self.gdrive_cb.isChecked()
        self.settings["gdrive_folder_name"] = self.folder_entry.text()
        self.settings["max_gdrive_backups"] = self.gdrive_max_spin.value()

        encrypt = self.encrypt_cb.isChecked()
        self.settings["encrypt_backups"] = encrypt
        if encrypt and not self.backup_utils.has_backup_password():
            pwd_dlg = PasswordDialog(self, title="Password backup", confirm=True)
            if pwd_dlg.result:
                self.backup_utils.set_backup_password(pwd_dlg.result)
            else:
                self.settings["encrypt_backups"] = False

        self.settings["backup_interval_minutes"] = self._interval_values[self.interval_combo.currentIndex()]

        self.backup_utils.save_settings(self.settings)
        QMessageBox.information(self, "Salvato", "Impostazioni backup salvate.")
        self.accept()


class BackupRestoreDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ripristina Backup")
        self.result: dict[str, Any] | None = None  # type: ignore[assignment]
        self.resize(650, 520)
        self.setModal(True)

        import backup_utils

        self.backup_utils: Any = backup_utils

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # Tabs: Locale / Google Drive
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # --- Tab Locale ---
        local_tab = QWidget()
        local_layout = QVBoxLayout(local_tab)
        local_layout.setContentsMargins(8, 8, 8, 8)

        self.backup_list = QListWidget()
        self.backup_list.currentRowChanged.connect(self._on_local_select)
        local_layout.addWidget(self.backup_list)

        detail_group = QGroupBox("Dettagli")
        detail_layout = QVBoxLayout(detail_group)
        self.detail_date = QLabel("Data: -")
        detail_layout.addWidget(self.detail_date)
        self.detail_size = QLabel("Dimensione: -")
        detail_layout.addWidget(self.detail_size)
        self.detail_notes = QLabel("Note: -")
        detail_layout.addWidget(self.detail_notes)
        self.detail_integrity = QLabel("Integrita': -")
        detail_layout.addWidget(self.detail_integrity)
        self.detail_checksum = QLabel("Checksum: -")
        detail_layout.addWidget(self.detail_checksum)
        self.detail_encrypted = QLabel("")
        detail_layout.addWidget(self.detail_encrypted)
        local_layout.addWidget(detail_group)

        self.tabs.addTab(local_tab, "Locale")

        # --- Tab Google Drive ---
        gdrive_tab = QWidget()
        gdrive_layout = QVBoxLayout(gdrive_tab)
        gdrive_layout.setContentsMargins(8, 8, 8, 8)

        self.gdrive_list = QListWidget()
        gdrive_layout.addWidget(self.gdrive_list)

        gdrive_detail = QGroupBox("Dettagli")
        gdrive_detail_layout = QVBoxLayout(gdrive_detail)
        self.gdrive_detail_date = QLabel("Data: -")
        gdrive_detail_layout.addWidget(self.gdrive_detail_date)
        self.gdrive_detail_size = QLabel("Dimensione: -")
        gdrive_detail_layout.addWidget(self.gdrive_detail_size)
        self.gdrive_detail_encrypted = QLabel("")
        gdrive_detail_layout.addWidget(self.gdrive_detail_encrypted)
        gdrive_layout.addWidget(gdrive_detail)

        self.gdrive_list.currentRowChanged.connect(self._on_gdrive_select)

        self.tabs.addTab(gdrive_tab, "Google Drive")

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        restore_btn = QPushButton("Ripristina")
        restore_btn.clicked.connect(self._restore)
        btn_layout.addWidget(restore_btn)
        close_btn = QPushButton("Chiudi")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        # Load local backups
        settings = backup_utils.get_settings()
        backup_dir = settings.get("local_backup_dir", db.BACKUP_DIR)
        self.backups: list[dict[str, Any]] = db.get_backups(backup_dir)
        for b in self.backups:
            enc_label = " [crittografato]" if b["encrypted"] else ""
            size_kb = b["size"] / 1024
            self.backup_list.addItem(f"{b['date_str']}  ({size_kb:.0f} KB){enc_label}")
        if not self.backups:
            self.backup_list.addItem("Nessun backup disponibile.")

        # Load GDrive backups
        self.gdrive_backups: list[dict[str, Any]] = []
        if backup_utils.is_gdrive_configured():
            self.gdrive_list.addItem("Caricamento...")
            QTimer.singleShot(100, self._load_gdrive_backups)
        else:
            self.gdrive_list.addItem("Google Drive non configurato.")
            self.gdrive_list.addItem("Vai in Backup > Impostazioni.")

        self.exec()

    def _load_gdrive_backups(self) -> None:
        self.gdrive_list.clear()
        self.gdrive_backups = self.backup_utils.list_gdrive_backups()
        if not self.gdrive_backups:
            self.gdrive_list.addItem("Nessun backup su Google Drive.")
            return
        for b in self.gdrive_backups:
            enc_label = " [crittografato]" if b["encrypted"] else ""
            size_kb = b["size"] / 1024
            self.gdrive_list.addItem(f"{b['date_str']}  ({size_kb:.0f} KB){enc_label}")

    def _on_local_select(self, row: int) -> None:
        if row < 0 or not self.backups:
            return
        b = self.backups[row]
        self.detail_date.setText(f"Data: {b['date_str']}")
        size_kb = b["size"] / 1024
        self.detail_size.setText(f"Dimensione: {size_kb:.1f} KB")

        if b["encrypted"]:
            self.detail_encrypted.setText("Crittografato: Si'")
            self.detail_notes.setText("Note: (richiede password)")
            self.detail_integrity.setText("Integrita': (richiede decrittografia)")
        else:
            self.detail_encrypted.setText("")
            count = self.backup_utils.get_note_count_from_backup(b["path"])
            self.detail_notes.setText(f"Note: {count}" if count >= 0 else "Note: errore lettura")
            ok, msg = self.backup_utils.verify_backup_integrity(b["path"])
            color = SUCCESS if ok else DANGER
            self.detail_integrity.setText(f"Integrita': {msg}")
            self.detail_integrity.setStyleSheet(f"color: {color};")

        ok_cs, msg_cs = self.backup_utils.verify_checksum(b["path"])
        if ok_cs is True:
            color_cs = SUCCESS
        elif ok_cs is False:
            color_cs = DANGER
        else:
            color_cs = FG_SECONDARY
        self.detail_checksum.setText(f"Checksum: {msg_cs}")
        self.detail_checksum.setStyleSheet(f"color: {color_cs};")

    def _on_gdrive_select(self, row: int) -> None:
        if row < 0 or not self.gdrive_backups:
            return
        b = self.gdrive_backups[row]
        self.gdrive_detail_date.setText(f"Data: {b['date_str']}")
        size_kb = b["size"] / 1024
        self.gdrive_detail_size.setText(f"Dimensione: {size_kb:.1f} KB")
        if b["encrypted"]:
            self.gdrive_detail_encrypted.setText("Crittografato: Si'")
        else:
            self.gdrive_detail_encrypted.setText("")

    def _restore(self) -> None:
        if self.tabs.currentIndex() == 0:
            self._restore_local()
        else:
            self._restore_gdrive()

    def _restore_local(self) -> None:
        row = self.backup_list.currentRow()
        if row < 0 or not self.backups:
            return
        b = self.backups[row]
        password = None

        if b["encrypted"]:
            pwd_dlg = PasswordDialog(self, title="Password backup")
            if not pwd_dlg.result:
                return
            password = pwd_dlg.result

        msg = (
            "Il database attuale verra' sostituito.\n"
            "Un backup di sicurezza verra' creato automaticamente.\n\n"
            "Continuare con il ripristino?"
        )
        if QMessageBox.question(self, "Conferma ripristino", msg) != QMessageBox.StandardButton.Yes:
            return

        self.result = {"path": b["path"], "password": password}
        self.accept()

    def _restore_gdrive(self) -> None:
        row = self.gdrive_list.currentRow()
        if row < 0 or not self.gdrive_backups:
            return
        b = self.gdrive_backups[row]

        msg = (
            "Il backup verra' scaricato da Google Drive.\n"
            "Il database attuale verra' sostituito.\n"
            "Un backup di sicurezza verra' creato automaticamente.\n\n"
            "Continuare?"
        )
        if QMessageBox.question(self, "Conferma ripristino", msg) != QMessageBox.StandardButton.Yes:
            return

        # Download to temp location
        import tempfile

        tmp_path = os.path.join(tempfile.gettempdir(), b["name"])
        ok, msg_dl = self.backup_utils.download_gdrive_backup(b["id"], tmp_path)
        if not ok:
            QMessageBox.critical(self, "Errore", msg_dl)
            return

        password = None
        if b["encrypted"]:
            pwd_dlg = PasswordDialog(self, title="Password backup")
            if not pwd_dlg.result:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                return
            password = pwd_dlg.result

        self.result = {"path": tmp_path, "password": password}
        self.accept()
