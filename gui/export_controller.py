"""Export HTML, PDF, .mynote and import (PySide6)."""

from __future__ import annotations

import html as html_mod
import os
import re
import sqlite3
import types
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog, QMessageBox

import database as db
import platform_utils

if TYPE_CHECKING:
    from gui import MyNotesApp


class ExportController:
    def __init__(self, app: MyNotesApp) -> None:
        self.app = app

    def export_html(self) -> None:
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if note is None:
            return
        path, _ = QFileDialog.getSaveFileName(app, "Esporta HTML", f"{note['title']}.html", "HTML (*.html)")
        if path:
            self._write_html(path, [note])
            app.statusBar().showMessage(f"Esportato: {path}")
            platform_utils.open_file(path)

    def export_all_html(self) -> None:
        app = self.app
        path, _ = QFileDialog.getSaveFileName(app, "Esporta tutte le note HTML", "MyNotes_export.html", "HTML (*.html)")
        if path:
            notes = db.get_all_notes()
            self._write_html(path, notes)
            app.statusBar().showMessage(f"Esportate {len(notes)} note: {path}")

    def _write_html(self, path: str, notes: list[sqlite3.Row]) -> None:
        import html as html_mod

        lines = [
            "<!DOCTYPE html><html><head><meta charset='utf-8'>",
            "<title>MyNotes Export</title>",
            "<style>body{font-family:sans-serif;max-width:800px;margin:auto;padding:20px}",
            ".note{border:1px solid #ddd;padding:20px;margin:20px 0;border-radius:8px}",
            ".note h2{margin-top:0;color:#333}.meta{color:#888;font-size:0.85em}",
            ".checklist-done{text-decoration:line-through;color:#888}</style></head><body>",
            "<h1>MyNotes Export</h1>",
        ]

        for note in notes:
            content = html_mod.escape(note["content"] or "")
            html_lines = []
            for line in content.split("\n"):
                if line.strip().startswith("[x]"):
                    html_lines.append(f'<div class="checklist-done">&#9745; {line.strip()[3:].strip()}</div>')
                elif line.strip().startswith("[ ]"):
                    html_lines.append(f"<div>&#9744; {line.strip()[3:].strip()}</div>")
                else:
                    html_lines.append(f"<p>{line}</p>" if line.strip() else "<br>")

            tags = db.get_note_tags(note["id"])
            tag_str = " ".join(f"#{t['name']}" for t in tags)

            lines.append('<div class="note">')
            lines.append(f"<h2>{html_mod.escape(note['title'])}</h2>")
            lines.append(f'<div class="meta">{note["created_at"][:10]} | {tag_str}</div>')
            lines.append("\n".join(html_lines))
            lines.append("</div>")

        lines.append("</body></html>")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def export_pdf(self) -> None:
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if note is None:
            return
        path, _ = QFileDialog.getSaveFileName(app, "Esporta PDF", f"{note['title']}.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas

            c = canvas.Canvas(path, pagesize=A4)
            w, h = A4
            y = h - 50
            c.setFont("Helvetica-Bold", 16)
            c.drawString(40, y, note["title"])
            y -= 20
            c.setFont("Helvetica", 9)
            c.drawString(40, y, f"Creata: {note['created_at'][:10]}  |  Modificata: {note['updated_at'][:10]}")
            y -= 30
            c.setFont("Helvetica", 11)
            for line in (note["content"] or "").split("\n"):
                if y < 50:
                    c.showPage()
                    y = h - 50
                    c.setFont("Helvetica", 11)
                c.drawString(40, y, line[:100])
                y -= 15
            c.save()
            app.statusBar().showMessage(f"PDF esportato: {path}")
        except ImportError:
            QMessageBox.warning(
                app,
                "PDF",
                "Per esportare in PDF serve reportlab.\n"
                "Installa con: pip install reportlab\n\n"
                "In alternativa usa l'esportazione HTML.",
            )

    def export_mynote(self) -> None:
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        if note is None:
            return
        path, _ = QFileDialog.getSaveFileName(app, "Condividi nota", f"{note['title']}.mynote", "MyNotes (*.mynote)")
        if path:
            try:
                db.export_note(app.current_note_id, path)
                app.statusBar().showMessage(f"Nota condivisa: {os.path.basename(path)}")
                QMessageBox.information(
                    app,
                    "Condividi",
                    f"Nota esportata:\n{path}\n\nCondividi questo file per importarlo in un'altra app MyNotes.",
                )
            except Exception as e:
                QMessageBox.critical(app, "Errore", f"Esportazione fallita: {e}")

    def import_mynote(self) -> None:
        app = self.app
        paths, _ = QFileDialog.getOpenFileNames(app, "Importa nota", "", "MyNotes (*.mynote);;Tutti (*.*)")
        if not paths:
            return
        imported = 0
        for path in paths:
            try:
                db.import_note(path, category_id=None)
                imported += 1
            except Exception as e:
                QMessageBox.critical(app, "Errore", f"Importazione fallita per {os.path.basename(path)}:\n{e}")
        if imported:
            app.notes_ctl.load_notes()
            app.statusBar().showMessage(f"Importate {imported} nota/e")
            QMessageBox.information(app, "Importa", f"{imported} nota/e importate con successo!")

    def import_markdown(self) -> None:
        app = self.app
        paths, _ = QFileDialog.getOpenFileNames(app, "Importa Markdown", "", "Markdown (*.md);;Tutti (*.*)")
        if not paths:
            return
        imported = 0
        for path in paths:
            try:
                title = Path(path).stem
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                db.add_note(title, content)
                imported += 1
            except Exception as e:
                QMessageBox.critical(app, "Errore", f"Importazione fallita per {os.path.basename(path)}:\n{e}")
        if imported:
            app.notes_ctl.load_notes()
            app.statusBar().showMessage(f"Importate {imported} nota/e Markdown")
            QMessageBox.information(app, "Importa Markdown", f"{imported} nota/e Markdown importate con successo!")

    # ------------------------------------------------------------------
    # Structured folder export
    # ------------------------------------------------------------------

    def export_all_structured(self) -> None:
        """Export all notes as HTML files in a folder tree mirroring the category hierarchy."""
        import markdown

        app = self.app
        base_dir = QFileDialog.getExistingDirectory(app, "Scegli cartella destinazione")
        if not base_dir:
            return

        # Create unique export folder
        folder_name = f"MyNotes_export_{date.today().isoformat()}"
        export_dir = Path(base_dir) / folder_name
        suffix = 1
        while export_dir.exists():
            suffix += 1
            export_dir = Path(base_dir) / f"{folder_name}_{suffix}"
        export_dir.mkdir(parents=True)

        notes = db.get_all_notes()
        if not notes:
            app.statusBar().showMessage("Nessuna nota da esportare.")
            return

        # Track used filenames per directory to handle duplicates
        used_names: dict[str, set[str]] = {}
        exported = 0

        for note in notes:
            # Determine folder path from category hierarchy
            cat_id: int | None = note["category_id"]
            if cat_id:
                cat_path = db.get_category_path(cat_id)
                rel_parts = [_sanitize_filename(c["name"]) for c in cat_path]
                note_dir = export_dir / Path(*rel_parts)
            else:
                note_dir = export_dir

            note_dir.mkdir(parents=True, exist_ok=True)
            dir_key = str(note_dir)
            if dir_key not in used_names:
                used_names[dir_key] = set()

            # Pick a unique filename
            base_name = _sanitize_filename(note["title"] or "Senza titolo")
            file_name = base_name
            counter = 2
            while file_name.lower() in used_names[dir_key]:
                file_name = f"{base_name}_{counter}"
                counter += 1
            used_names[dir_key].add(file_name.lower())

            tags = db.get_note_tags(note["id"])
            html_content = _build_note_html(note, tags, markdown)
            (note_dir / f"{file_name}.html").write_text(html_content, encoding="utf-8")
            exported += 1

        app.statusBar().showMessage(f"Esportate {exported} note in {export_dir}")


_INVALID_CHARS_RE = re.compile(r'[<>:"/\\|?*]')


def _sanitize_filename(name: str) -> str:
    """Remove/replace characters invalid in file/folder names."""
    sanitized = _INVALID_CHARS_RE.sub("_", name).strip().strip(".")
    return sanitized or "Senza_nome"


def _build_note_html(note: sqlite3.Row, tags: list[sqlite3.Row], markdown_mod: types.ModuleType) -> str:
    """Generate a styled standalone HTML page for a note."""
    title = html_mod.escape(note["title"] or "Senza titolo")
    created = (note["created_at"] or "")[:10]
    updated = (note["updated_at"] or "")[:10]
    tag_str = " ".join(f"#{html_mod.escape(t['name'])}" for t in tags)

    if note["is_encrypted"]:
        body = "<p><em>[Nota criptata]</em></p>"
    else:
        content = note["content"] or ""
        body = markdown_mod.markdown(content, extensions=["fenced_code", "tables", "nl2br"])

    return (
        "<!DOCTYPE html>\n<html>\n<head>\n<meta charset='utf-8'>\n"
        f"<title>{title}</title>\n"
        "<style>\n"
        "body { font-family: sans-serif; max-width: 800px; margin: auto; padding: 20px; }\n"
        "h1 { color: #333; }\n"
        ".meta { color: #888; font-size: 0.85em; margin-bottom: 1em; }\n"
        "pre { background: #f4f4f4; padding: 12px; border-radius: 4px; overflow-x: auto; }\n"
        "code { background: #f4f4f4; padding: 2px 4px; border-radius: 3px; }\n"
        "table { border-collapse: collapse; }\n"
        "th, td { border: 1px solid #ddd; padding: 8px; }\n"
        "</style>\n</head>\n<body>\n"
        f"<h1>{title}</h1>\n"
        f'<div class="meta">Creata: {created} | Modificata: {updated}'
        f"{(' | ' + tag_str) if tag_str else ''}</div>\n"
        f"{body}\n"
        "</body>\n</html>"
    )
