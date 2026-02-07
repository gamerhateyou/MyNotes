"""All dialog windows (PySide6 QDialog)."""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QCheckBox, QListWidget, QPlainTextEdit, QMessageBox,
    QFileDialog, QGroupBox, QSpinBox, QFrame, QWidget, QTabWidget
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

import database as db
import platform_utils
import audio_utils
from gui.constants import (UI_FONT, FONT_SM, FONT_BASE,
                           BG_SURFACE, BG_ELEVATED,
                           FG_PRIMARY, FG_SECONDARY, FG_MUTED,
                           ACCENT, SUCCESS, DANGER,
                           SELECT_BG, SELECT_FG)


class CategoryDialog(QDialog):
    def __init__(self, parent, title="Nuova Categoria", initial_name=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.result = None
        self.setFixedWidth(350)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel("Nome categoria:"))
        self.entry = QLineEdit()
        self.entry.setText(initial_name)
        layout.addWidget(self.entry)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(ok_btn)
        cancel_btn = QPushButton("Annulla")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.entry.setFocus()
        self.exec()

    def _on_ok(self):
        name = self.entry.text().strip()
        if name:
            self.result = name
            self.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._on_ok()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)


class NoteDialog(QDialog):
    def __init__(self, parent, categories):
        super().__init__(parent)
        self.setWindowTitle("Nuova Nota")
        self.result = None
        self.setFixedWidth(400)
        self.setModal(True)
        self.categories = categories

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel("Titolo:"))
        self.title_entry = QLineEdit()
        layout.addWidget(self.title_entry)

        layout.addWidget(QLabel("Categoria:"))
        self.cat_combo = QComboBox()
        self.cat_combo.addItem("(Nessuna)")
        for c in categories:
            self.cat_combo.addItem(c["name"])
        layout.addWidget(self.cat_combo)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        create_btn = QPushButton("Crea")
        create_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(create_btn)
        cancel_btn = QPushButton("Annulla")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.title_entry.setFocus()
        self.exec()

    def _on_ok(self):
        title = self.title_entry.text().strip()
        if not title:
            QMessageBox.warning(self, "Attenzione", "Inserisci un titolo.")
            return
        cat_id = None
        idx = self.cat_combo.currentIndex()
        if idx > 0:
            cat_id = self.categories[idx - 1]["id"]
        self.result = {"title": title, "category_id": cat_id}
        self.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._on_ok()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)


class TagManagerDialog(QDialog):
    def __init__(self, parent, note_id):
        super().__init__(parent)
        self.setWindowTitle("Gestione Tag")
        self.note_id = note_id
        self.setFixedWidth(350)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel("Nuovo tag:"))
        self.new_tag_entry = QLineEdit()
        add_layout.addWidget(self.new_tag_entry)
        add_btn = QPushButton("Aggiungi")
        add_btn.clicked.connect(self._add_tag)
        add_layout.addWidget(add_btn)
        layout.addLayout(add_layout)

        layout.addWidget(QLabel("Tag disponibili:"))
        self.check_widget = QWidget()
        self.check_layout = QVBoxLayout(self.check_widget)
        self.check_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.check_widget)

        self.tag_vars = {}
        self._load_tags()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Chiudi")
        close_btn.clicked.connect(self._on_close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.exec()

    def _load_tags(self):
        while self.check_layout.count():
            child = self.check_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        all_tags = db.get_all_tags()
        note_tags = db.get_note_tags(self.note_id)
        note_tag_ids = {t["id"] for t in note_tags}
        self.tag_vars = {}
        for tag in all_tags:
            cb = QCheckBox(tag["name"])
            cb.setChecked(tag["id"] in note_tag_ids)
            self.tag_vars[tag["id"]] = cb
            self.check_layout.addWidget(cb)
        if not all_tags:
            self.check_layout.addWidget(QLabel("Nessun tag creato."))

    def _add_tag(self):
        name = self.new_tag_entry.text().strip()
        if name:
            db.add_tag(name)
            self.new_tag_entry.clear()
            self._load_tags()

    def _on_close(self):
        selected_ids = [tid for tid, cb in self.tag_vars.items() if cb.isChecked()]
        db.set_note_tags(self.note_id, selected_ids)
        self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._on_close()
        else:
            super().keyPressEvent(event)


class AttachmentDialog(QDialog):
    def __init__(self, parent, note_id):
        super().__init__(parent)
        self.setWindowTitle("Allegati")
        self.note_id = note_id
        self.resize(450, 350)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        toolbar = QHBoxLayout()
        add_btn = QPushButton("Aggiungi file...")
        add_btn.clicked.connect(self._add_file)
        toolbar.addWidget(add_btn)
        remove_btn = QPushButton("Rimuovi selezionato")
        remove_btn.clicked.connect(self._remove_file)
        toolbar.addWidget(remove_btn)
        open_btn = QPushButton("Apri file")
        open_btn.clicked.connect(self._open_file)
        toolbar.addWidget(open_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.listbox = QListWidget()
        layout.addWidget(self.listbox)

        self.attachments = []
        self._load_attachments()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Chiudi")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.exec()

    def _load_attachments(self):
        self.listbox.clear()
        self.attachments = db.get_note_attachments(self.note_id)
        for att in self.attachments:
            self.listbox.addItem(f"{att['original_name']}  ({att['added_at'][:10]})")

    def _add_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona file da allegare")
        if path:
            db.add_attachment(self.note_id, path)
            self._load_attachments()

    def _remove_file(self):
        row = self.listbox.currentRow()
        if row < 0:
            return
        att = self.attachments[row]
        if QMessageBox.question(
            self, "Conferma",
            f"Rimuovere '{att['original_name']}'?"
        ) == QMessageBox.Yes:
            db.delete_attachment(att["id"])
            self._load_attachments()

    def _open_file(self):
        row = self.listbox.currentRow()
        if row < 0:
            return
        att = self.attachments[row]
        path = os.path.join(db.ATTACHMENTS_DIR, att["filename"])
        if not platform_utils.open_file(path):
            QMessageBox.critical(self, "Errore", "Impossibile aprire il file.")


class VersionHistoryDialog(QDialog):
    def __init__(self, parent, note_id):
        super().__init__(parent)
        self.setWindowTitle("Cronologia versioni")
        self.note_id = note_id
        self.result = None
        self.resize(600, 450)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        layout.addWidget(QLabel("Versioni salvate:"))

        self.version_list = QListWidget()
        self.version_list.currentRowChanged.connect(self._on_select)
        layout.addWidget(self.version_list)

        layout.addWidget(QLabel("Anteprima:"))
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(200)
        layout.addWidget(self.preview)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        restore_btn = QPushButton("Ripristina questa versione")
        restore_btn.clicked.connect(self._restore)
        btn_layout.addWidget(restore_btn)
        close_btn = QPushButton("Chiudi")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.versions = db.get_note_versions(note_id)
        for v in self.versions:
            date = v["saved_at"][:19].replace("T", " ")
            title = v["title"][:40]
            self.version_list.addItem(f"[{date}]  {title}")

        if not self.versions:
            self.version_list.addItem("Nessuna versione precedente salvata.")

        self.exec()

    def _on_select(self, row):
        if row < 0 or not self.versions:
            return
        ver = self.versions[row]
        self.preview.setPlainText(ver["content"] or "")

    def _restore(self):
        row = self.version_list.currentRow()
        if row < 0 or not self.versions:
            return
        ver = self.versions[row]
        if QMessageBox.question(
            self, "Ripristina",
            "Ripristinare questa versione?\nLa versione attuale verra' salvata."
        ) == QMessageBox.Yes:
            note = db.get_note(self.note_id)
            if note:
                db.save_version(self.note_id, note["title"], note["content"])
            db.restore_version(self.note_id, ver["id"])
            self.result = True
            self.accept()


class PasswordDialog(QDialog):
    def __init__(self, parent, title="Password", confirm=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.result = None
        self.setFixedWidth(350)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel("Password:"))
        self.pw_entry = QLineEdit()
        self.pw_entry.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.pw_entry)
        self.pw_entry.setFocus()

        self.pw_confirm = None
        if confirm:
            layout.addWidget(QLabel("Conferma password:"))
            self.pw_confirm = QLineEdit()
            self.pw_confirm.setEchoMode(QLineEdit.Password)
            layout.addWidget(self.pw_confirm)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(ok_btn)
        cancel_btn = QPushButton("Annulla")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.exec()

    def _on_ok(self):
        pw = self.pw_entry.text()
        if not pw:
            QMessageBox.warning(self, "Attenzione", "Inserisci una password.")
            return
        if self.pw_confirm is not None:
            if pw != self.pw_confirm.text():
                QMessageBox.warning(self, "Attenzione", "Le password non coincidono.")
                return
        self.result = pw
        self.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._on_ok()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)


class AudioRecordDialog(QDialog):
    def __init__(self, parent, mode="record", audio_path=None):
        super().__init__(parent)
        self.mode = mode
        self.audio_path = audio_path
        self.result = None
        self._timer = None
        self._elapsed = 0
        self._recording = False
        self._temp_path = None
        self.setFixedWidth(400)
        self.setModal(True)

        if mode == "record":
            self.setWindowTitle("Registra Audio")
            self._build_record_ui()
        else:
            self.setWindowTitle("Descrizione Audio")
            self._build_describe_ui()

        self.exec()

    def _build_record_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel("Descrizione (opzionale):"))
        self.desc_entry = QLineEdit()
        layout.addWidget(self.desc_entry)

        self.timer_label = QLabel("00:00")
        self.timer_label.setFont(QFont(UI_FONT, 18, QFont.Bold))
        self.timer_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.timer_label)

        self.status_label = QLabel("Pronto per registrare")
        self.status_label.setStyleSheet(f"color: {FG_SECONDARY};")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        rec_layout = QHBoxLayout()
        self.rec_btn = QPushButton("Registra")
        self.rec_btn.clicked.connect(self._toggle_record)
        rec_layout.addWidget(self.rec_btn)
        self.preview_btn = QPushButton("Anteprima")
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self._preview)
        rec_layout.addWidget(self.preview_btn)
        layout.addLayout(rec_layout)

        if not audio_utils.is_available():
            self.rec_btn.setEnabled(False)
            self.status_label.setText(
                "Libreria 'sounddevice' non installata.\npip install sounddevice")
            self.status_label.setStyleSheet(f"color: {DANGER};")

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_btn = QPushButton("Salva")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self.save_btn)
        cancel_btn = QPushButton("Annulla")
        cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _build_describe_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        filename = os.path.basename(self.audio_path) if self.audio_path else ""
        layout.addWidget(QLabel(f"File: {filename}"))

        layout.addWidget(QLabel("Descrizione (opzionale):"))
        self.desc_entry = QLineEdit()
        layout.addWidget(self.desc_entry)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(ok_btn)
        cancel_btn = QPushButton("Annulla")
        cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _toggle_record(self):
        if not self._recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        self._temp_path = audio_utils.get_temp_wav_path()
        try:
            audio_utils.record_audio()
        except Exception as e:
            QMessageBox.critical(self, "Errore",
                                 f"Impossibile avviare la registrazione:\n{e}")
            return
        self._recording = True
        self._elapsed = 0
        self.rec_btn.setText("Stop")
        self.preview_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.status_label.setText("Registrazione in corso...")
        self.status_label.setStyleSheet(f"color: {DANGER};")
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_timer)
        self._timer.start(1000)

    def _stop_recording(self):
        if self._timer:
            self._timer.stop()
            self._timer = None
        self._recording = False
        audio_utils.stop_recording(self._temp_path)
        self.rec_btn.setText("Registra")
        self.preview_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.status_label.setText("Registrazione completata")
        self.status_label.setStyleSheet(f"color: {SUCCESS};")

    def _update_timer(self):
        self._elapsed += 1
        mins, secs = divmod(self._elapsed, 60)
        self.timer_label.setText(f"{mins:02d}:{secs:02d}")

    def _preview(self):
        if self._temp_path and os.path.exists(self._temp_path):
            platform_utils.open_file(self._temp_path)

    def _on_save(self):
        if self._recording:
            self._stop_recording()

        desc = self.desc_entry.text().strip()

        if self.mode == "record":
            if not self._temp_path or not os.path.exists(self._temp_path):
                QMessageBox.warning(self, "Attenzione",
                                    "Nessuna registrazione effettuata.")
                return
            self.result = {"path": self._temp_path, "description": desc}
        else:
            self.result = {"path": self.audio_path, "description": desc}
        self.accept()

    def _on_cancel(self):
        if self._recording:
            self._stop_recording()
        if self.mode == "record" and self._temp_path and os.path.exists(self._temp_path):
            try:
                os.remove(self._temp_path)
            except OSError:
                pass
        self.result = None
        self.reject()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._on_cancel()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter) and self.mode == "describe":
            self._on_save()
        else:
            super().keyPressEvent(event)


class BackupSettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Impostazioni Backup")
        self.setMinimumWidth(500)
        self.setModal(True)

        import backup_utils
        self.backup_utils = backup_utils
        self.settings = backup_utils.get_settings()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # --- Local Backup ---
        local_label = QLabel("Backup Locale")
        local_label.setFont(QFont(UI_FONT, FONT_BASE, QFont.Bold))
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
        sep1.setFrameShape(QFrame.HLine)
        layout.addWidget(sep1)

        gdrive_label = QLabel("Google Drive")
        gdrive_label.setFont(QFont(UI_FONT, FONT_BASE, QFont.Bold))
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
        self.folder_entry = QLineEdit(
            self.settings.get("gdrive_folder_name", "MyNotes Backup"))
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
        sep2.setFrameShape(QFrame.HLine)
        layout.addWidget(sep2)

        enc_label = QLabel("Crittografia")
        enc_label.setFont(QFont(UI_FONT, FONT_BASE, QFont.Bold))
        layout.addWidget(enc_label)

        self.encrypt_cb = QCheckBox("Cripta backup con password")
        self.encrypt_cb.setChecked(self.settings.get("encrypt_backups", False))
        layout.addWidget(self.encrypt_cb)

        pw_set = backup_utils._get_backup_password()
        pw_status = "Password impostata" if pw_set else "Password non impostata"
        pw_color = SUCCESS if pw_set else FG_SECONDARY
        self.pw_status_label = QLabel(pw_status)
        self.pw_status_label.setStyleSheet(f"color: {pw_color};")
        layout.addWidget(self.pw_status_label)

        # --- Scheduler ---
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        layout.addWidget(sep3)

        sched_label = QLabel("Backup Automatico")
        sched_label.setFont(QFont(UI_FONT, FONT_BASE, QFont.Bold))
        layout.addWidget(sched_label)

        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Intervallo backup:"))
        self._interval_labels = ["Disabilitato", "30 minuti", "1 ora", "2 ore",
                                 "4 ore", "8 ore", "12 ore", "24 ore"]
        self._interval_values = [0, 30, 60, 120, 240, 480, 720, 1440]
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(self._interval_labels)
        current_interval = self.settings.get("backup_interval_minutes", 0)
        idx = (self._interval_values.index(current_interval)
               if current_interval in self._interval_values else 0)
        self.interval_combo.setCurrentIndex(idx)
        interval_layout.addWidget(self.interval_combo)
        interval_layout.addStretch()
        layout.addLayout(interval_layout)

        last_backup = self.settings.get("last_backup_time", "")
        last_text = (f"Ultimo backup: {last_backup}"
                     if last_backup else "Ultimo backup: mai")
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

    def _update_gdrive_status(self):
        if self.backup_utils.is_gdrive_configured():
            self.gdrive_status_label.setText("Connesso a Google Drive")
            self.gdrive_status_label.setStyleSheet(f"color: {SUCCESS};")
            self.auth_btn.setText("Disconnetti")
        else:
            self.gdrive_status_label.setText("Non connesso")
            self.gdrive_status_label.setStyleSheet(f"color: {FG_SECONDARY};")
            self.auth_btn.setText("Accedi con Google")

    def _toggle_gdrive_auth(self):
        if self.backup_utils.is_gdrive_configured():
            if QMessageBox.question(
                self, "Disconnetti",
                "Rimuovere l'autorizzazione Google Drive?"
            ) == QMessageBox.Yes:
                self.backup_utils.gdrive_disconnect()
                self.gdrive_cb.setChecked(False)
                self._update_gdrive_status()
        else:
            self.auth_btn.setEnabled(False)
            self.auth_btn.setText("Autorizzazione in corso...")

            import threading
            def _do_auth():
                success, msg = self.backup_utils.gdrive_authorize()
                QTimer.singleShot(0, lambda: self._auth_done(success, msg))

            threading.Thread(target=_do_auth, daemon=True).start()

    def _auth_done(self, success, msg):
        self.auth_btn.setEnabled(True)
        if success:
            QMessageBox.information(self, "Google Drive", msg)
        else:
            QMessageBox.critical(self, "Errore", msg)
        self._update_gdrive_status()

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Cartella backup")
        if d:
            self.dir_entry.setText(d)

    def _save(self):
        self.settings["auto_backup"] = self.auto_cb.isChecked()
        self.settings["local_backup_dir"] = self.dir_entry.text()
        self.settings["max_local_backups"] = self.max_spin.value()
        self.settings["retention_days"] = self.retention_spin.value()
        self.settings["gdrive_enabled"] = self.gdrive_cb.isChecked()
        self.settings["gdrive_folder_name"] = self.folder_entry.text()
        self.settings["max_gdrive_backups"] = self.gdrive_max_spin.value()

        encrypt = self.encrypt_cb.isChecked()
        self.settings["encrypt_backups"] = encrypt
        if encrypt and not self.backup_utils._get_backup_password():
            pwd_dlg = PasswordDialog(self, title="Password backup", confirm=True)
            if pwd_dlg.result:
                self.backup_utils.set_backup_password(pwd_dlg.result)
            else:
                self.settings["encrypt_backups"] = False

        self.settings["backup_interval_minutes"] = \
            self._interval_values[self.interval_combo.currentIndex()]

        self.backup_utils.save_settings(self.settings)
        QMessageBox.information(self, "Salvato", "Impostazioni backup salvate.")
        self.accept()


class BackupRestoreDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Ripristina Backup")
        self.result = None
        self.resize(650, 520)
        self.setModal(True)

        import backup_utils
        self.backup_utils = backup_utils

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
        self.backups = db.get_backups(backup_dir)
        for b in self.backups:
            enc_label = " [crittografato]" if b["encrypted"] else ""
            size_kb = b["size"] / 1024
            self.backup_list.addItem(
                f"{b['date_str']}  ({size_kb:.0f} KB){enc_label}"
            )
        if not self.backups:
            self.backup_list.addItem("Nessun backup disponibile.")

        # Load GDrive backups
        self.gdrive_backups = []
        if backup_utils.is_gdrive_configured():
            self.gdrive_list.addItem("Caricamento...")
            QTimer.singleShot(100, self._load_gdrive_backups)
        else:
            self.gdrive_list.addItem("Google Drive non configurato.")
            self.gdrive_list.addItem("Vai in Backup > Impostazioni.")

        self.exec()

    def _load_gdrive_backups(self):
        self.gdrive_list.clear()
        self.gdrive_backups = self.backup_utils.list_gdrive_backups()
        if not self.gdrive_backups:
            self.gdrive_list.addItem("Nessun backup su Google Drive.")
            return
        for b in self.gdrive_backups:
            enc_label = " [crittografato]" if b["encrypted"] else ""
            size_kb = b["size"] / 1024
            self.gdrive_list.addItem(
                f"{b['date_str']}  ({size_kb:.0f} KB){enc_label}"
            )

    def _on_local_select(self, row):
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
            self.detail_notes.setText(
                f"Note: {count}" if count >= 0 else "Note: errore lettura")
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

    def _on_gdrive_select(self, row):
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

    def _restore(self):
        if self.tabs.currentIndex() == 0:
            self._restore_local()
        else:
            self._restore_gdrive()

    def _restore_local(self):
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

        msg = ("Il database attuale verra' sostituito.\n"
               "Un backup di sicurezza verra' creato automaticamente.\n\n"
               "Continuare con il ripristino?")
        if QMessageBox.question(
            self, "Conferma ripristino", msg
        ) != QMessageBox.Yes:
            return

        self.result = {"path": b["path"], "password": password}
        self.accept()

    def _restore_gdrive(self):
        row = self.gdrive_list.currentRow()
        if row < 0 or not self.gdrive_backups:
            return
        b = self.gdrive_backups[row]

        msg = ("Il backup verra' scaricato da Google Drive.\n"
               "Il database attuale verra' sostituito.\n"
               "Un backup di sicurezza verra' creato automaticamente.\n\n"
               "Continuare?")
        if QMessageBox.question(
            self, "Conferma ripristino", msg
        ) != QMessageBox.Yes:
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
