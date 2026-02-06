import sqlite3
import os
import sys
from datetime import datetime

# Portable: tutto relativo alla cartella dell'app
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(APP_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "mynotes.db")
ATTACHMENTS_DIR = os.path.join(DATA_DIR, "attachments")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            category_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS note_tags (
            note_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (note_id, tag_id),
            FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            added_at TEXT NOT NULL,
            FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()


# --- Categories ---

def get_all_categories():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
    conn.close()
    return rows


def add_category(name):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()


def rename_category(cat_id, new_name):
    conn = get_connection()
    try:
        conn.execute("UPDATE categories SET name = ? WHERE id = ?", (new_name, cat_id))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()


def delete_category(cat_id):
    conn = get_connection()
    conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    conn.commit()
    conn.close()


# --- Notes ---

def get_all_notes(category_id=None, tag_id=None, search_query=None):
    conn = get_connection()
    query = "SELECT DISTINCT n.* FROM notes n"
    joins = []
    conditions = []
    params = []

    if tag_id is not None:
        joins.append("JOIN note_tags nt ON n.id = nt.note_id")
        conditions.append("nt.tag_id = ?")
        params.append(tag_id)

    if category_id is not None:
        conditions.append("n.category_id = ?")
        params.append(category_id)

    if search_query:
        conditions.append("(n.title LIKE ? OR n.content LIKE ?)")
        like = f"%{search_query}%"
        params.extend([like, like])

    if joins:
        query += " " + " ".join(joins)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY n.updated_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def get_note(note_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    conn.close()
    return row


def add_note(title, content="", category_id=None):
    now = datetime.now().isoformat()
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO notes (title, content, category_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (title, content, category_id, now, now),
    )
    note_id = cur.lastrowid
    conn.commit()
    conn.close()
    return note_id


def update_note(note_id, title=None, content=None, category_id=None):
    conn = get_connection()
    note = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    if not note:
        conn.close()
        return

    new_title = title if title is not None else note["title"]
    new_content = content if content is not None else note["content"]
    new_cat = category_id if category_id is not None else note["category_id"]
    now = datetime.now().isoformat()

    conn.execute(
        "UPDATE notes SET title = ?, content = ?, category_id = ?, updated_at = ? WHERE id = ?",
        (new_title, new_content, new_cat, now, note_id),
    )
    conn.commit()
    conn.close()


def delete_note(note_id):
    conn = get_connection()
    attachments = conn.execute("SELECT filename FROM attachments WHERE note_id = ?", (note_id,)).fetchall()
    for att in attachments:
        path = os.path.join(ATTACHMENTS_DIR, att["filename"])
        if os.path.exists(path):
            os.remove(path)
    conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()


# --- Tags ---

def get_all_tags():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM tags ORDER BY name").fetchall()
    conn.close()
    return rows


def add_tag(name):
    conn = get_connection()
    try:
        cur = conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
        tag_id = cur.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()["id"]
    finally:
        conn.close()
    return tag_id


def delete_tag(tag_id):
    conn = get_connection()
    conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    conn.commit()
    conn.close()


def get_note_tags(note_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT t.* FROM tags t JOIN note_tags nt ON t.id = nt.tag_id WHERE nt.note_id = ? ORDER BY t.name",
        (note_id,),
    ).fetchall()
    conn.close()
    return rows


def set_note_tags(note_id, tag_ids):
    conn = get_connection()
    conn.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
    for tid in tag_ids:
        conn.execute("INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)", (note_id, tid))
    conn.commit()
    conn.close()


# --- Attachments ---

def get_note_attachments(note_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM attachments WHERE note_id = ? ORDER BY added_at DESC", (note_id,)
    ).fetchall()
    conn.close()
    return rows


def add_attachment(note_id, source_path):
    import shutil
    import uuid

    original_name = os.path.basename(source_path)
    ext = os.path.splitext(original_name)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(ATTACHMENTS_DIR, filename)
    shutil.copy2(source_path, dest)

    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO attachments (note_id, filename, original_name, added_at) VALUES (?, ?, ?, ?)",
        (note_id, filename, original_name, now),
    )
    conn.commit()
    conn.close()
    return filename


def delete_attachment(att_id):
    conn = get_connection()
    att = conn.execute("SELECT filename FROM attachments WHERE id = ?", (att_id,)).fetchone()
    if att:
        path = os.path.join(ATTACHMENTS_DIR, att["filename"])
        if os.path.exists(path):
            os.remove(path)
        conn.execute("DELETE FROM attachments WHERE id = ?", (att_id,))
        conn.commit()
    conn.close()
