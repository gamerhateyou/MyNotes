"""Audio recording dialog."""

import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QLineEdit, QPushButton, QMessageBox, QFrame)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

import audio_utils
import platform_utils
from gui.constants import (UI_FONT, FG_SECONDARY, DANGER, SUCCESS)


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
