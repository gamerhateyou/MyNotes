"""Export HTML, PDF, .mynote and import."""

import os
import tkinter as tk
from tkinter import messagebox, filedialog
import database as db
import platform_utils


class ExportController:
    def __init__(self, app):
        self.app = app

    def export_html(self):
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        path = filedialog.asksaveasfilename(
            parent=app.root, title="Esporta HTML",
            defaultextension=".html", initialfile=f"{note['title']}.html",
            filetypes=[("HTML", "*.html")]
        )
        if path:
            self._write_html(path, [note])
            app.status_var.set(f"Esportato: {path}")
            platform_utils.open_file(path)

    def export_all_html(self):
        app = self.app
        path = filedialog.asksaveasfilename(
            parent=app.root, title="Esporta tutte le note HTML",
            defaultextension=".html", initialfile="MyNotes_export.html",
            filetypes=[("HTML", "*.html")]
        )
        if path:
            notes = db.get_all_notes()
            self._write_html(path, notes)
            app.status_var.set(f"Esportate {len(notes)} note: {path}")

    def _write_html(self, path, notes):
        import html as html_mod
        lines = ["<!DOCTYPE html><html><head><meta charset='utf-8'>",
                 "<title>MyNotes Export</title>",
                 "<style>body{font-family:sans-serif;max-width:800px;margin:auto;padding:20px}",
                 ".note{border:1px solid #ddd;padding:20px;margin:20px 0;border-radius:8px}",
                 ".note h2{margin-top:0;color:#333}.meta{color:#888;font-size:0.85em}",
                 ".checklist-done{text-decoration:line-through;color:#888}</style></head><body>",
                 "<h1>MyNotes Export</h1>"]

        for note in notes:
            content = html_mod.escape(note["content"] or "")
            html_lines = []
            for line in content.split("\n"):
                if line.strip().startswith("[x]"):
                    html_lines.append(f'<div class="checklist-done">&#9745; {line.strip()[3:].strip()}</div>')
                elif line.strip().startswith("[ ]"):
                    html_lines.append(f'<div>&#9744; {line.strip()[3:].strip()}</div>')
                else:
                    html_lines.append(f"<p>{line}</p>" if line.strip() else "<br>")

            tags = db.get_note_tags(note["id"])
            tag_str = " ".join(f"#{t['name']}" for t in tags)

            lines.append(f'<div class="note">')
            lines.append(f'<h2>{html_mod.escape(note["title"])}</h2>')
            lines.append(f'<div class="meta">{note["created_at"][:10]} | {tag_str}</div>')
            lines.append("\n".join(html_lines))
            lines.append("</div>")

        lines.append("</body></html>")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def export_pdf(self):
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        path = filedialog.asksaveasfilename(
            parent=app.root, title="Esporta PDF",
            defaultextension=".pdf", initialfile=f"{note['title']}.pdf",
            filetypes=[("PDF", "*.pdf")]
        )
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
            app.status_var.set(f"PDF esportato: {path}")
        except ImportError:
            messagebox.showwarning(
                "PDF",
                "Per esportare in PDF serve reportlab.\n"
                "Installa con: pip install reportlab\n\n"
                "In alternativa usa l'esportazione HTML.",
                parent=app.root
            )

    def export_mynote(self):
        app = self.app
        if app.current_note_id is None:
            return
        note = db.get_note(app.current_note_id)
        path = filedialog.asksaveasfilename(
            parent=app.root, title="Condividi nota",
            defaultextension=".mynote", initialfile=f"{note['title']}.mynote",
            filetypes=[("MyNotes", "*.mynote")]
        )
        if path:
            try:
                db.export_note(app.current_note_id, path)
                app.status_var.set(f"Nota condivisa: {os.path.basename(path)}")
                messagebox.showinfo("Condividi", f"Nota esportata:\n{path}\n\nCondividi questo file per importarlo in un'altra app MyNotes.", parent=app.root)
            except Exception as e:
                messagebox.showerror("Errore", f"Esportazione fallita: {e}", parent=app.root)

    def import_mynote(self):
        app = self.app
        paths = filedialog.askopenfilenames(
            parent=app.root, title="Importa nota",
            filetypes=[("MyNotes", "*.mynote"), ("Tutti", "*.*")]
        )
        if not paths:
            return
        imported = 0
        for path in paths:
            try:
                db.import_note(path, category_id=None)
                imported += 1
            except Exception as e:
                messagebox.showerror("Errore", f"Importazione fallita per {os.path.basename(path)}:\n{e}", parent=app.root)
        if imported:
            app.notes_ctl.load_notes()
            app.status_var.set(f"Importate {imported} nota/e")
            messagebox.showinfo("Importa", f"{imported} nota/e importate con successo!", parent=app.root)
