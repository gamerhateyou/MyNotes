import sqlite3
import os
import sys
from datetime import datetime, timedelta

# Portable: tutto relativo alla cartella dell'app
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(APP_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "mynotes.db")
ATTACHMENTS_DIR = os.path.join(DATA_DIR, "attachments")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
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
            is_pinned INTEGER DEFAULT 0,
            is_favorite INTEGER DEFAULT 0,
            is_deleted INTEGER DEFAULT 0,
            deleted_at TEXT,
            is_encrypted INTEGER DEFAULT 0,
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

        CREATE TABLE IF NOT EXISTS note_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            saved_at TEXT NOT NULL,
            FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
        );
    """)
    # Migration: add columns if missing (for existing databases)
    _migrate(conn)
    conn.commit()
    conn.close()
    # Auto-purge old trash
    purge_trash(30)


def _migrate(conn):
    """Add new columns to existing databases."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(notes)").fetchall()}
    migrations = [
        ("is_pinned", "INTEGER DEFAULT 0"),
        ("is_favorite", "INTEGER DEFAULT 0"),
        ("is_deleted", "INTEGER DEFAULT 0"),
        ("deleted_at", "TEXT"),
        ("is_encrypted", "INTEGER DEFAULT 0"),
    ]
    for col, col_type in migrations:
        if col not in existing:
            conn.execute(f"ALTER TABLE notes ADD COLUMN {col} {col_type}")


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

def get_all_notes(category_id=None, tag_id=None, search_query=None,
                  show_deleted=False, favorites_only=False):
    conn = get_connection()
    query = "SELECT DISTINCT n.* FROM notes n"
    joins = []
    conditions = []
    params = []

    if show_deleted:
        conditions.append("n.is_deleted = 1")
    else:
        conditions.append("n.is_deleted = 0")

    if favorites_only:
        conditions.append("n.is_favorite = 1")

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

    # Pinned first, then by date
    query += " ORDER BY n.is_pinned DESC, n.updated_at DESC"
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


def toggle_pin(note_id):
    conn = get_connection()
    note = conn.execute("SELECT is_pinned FROM notes WHERE id = ?", (note_id,)).fetchone()
    if note:
        new_val = 0 if note["is_pinned"] else 1
        conn.execute("UPDATE notes SET is_pinned = ? WHERE id = ?", (new_val, note_id))
        conn.commit()
    conn.close()


def toggle_favorite(note_id):
    conn = get_connection()
    note = conn.execute("SELECT is_favorite FROM notes WHERE id = ?", (note_id,)).fetchone()
    if note:
        new_val = 0 if note["is_favorite"] else 1
        conn.execute("UPDATE notes SET is_favorite = ? WHERE id = ?", (new_val, note_id))
        conn.commit()
    conn.close()


# --- Trash ---

def soft_delete_note(note_id):
    """Move note to trash."""
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute("UPDATE notes SET is_deleted = 1, deleted_at = ? WHERE id = ?", (now, note_id))
    conn.commit()
    conn.close()


def restore_note(note_id):
    """Restore note from trash."""
    conn = get_connection()
    conn.execute("UPDATE notes SET is_deleted = 0, deleted_at = NULL WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()


def permanent_delete_note(note_id):
    """Permanently delete note and its attachments."""
    conn = get_connection()
    attachments = conn.execute("SELECT filename FROM attachments WHERE note_id = ?", (note_id,)).fetchall()
    for att in attachments:
        path = os.path.join(ATTACHMENTS_DIR, att["filename"])
        if os.path.exists(path):
            os.remove(path)
    conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()


def purge_trash(days=30):
    """Permanently delete notes in trash older than N days."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = get_connection()
    old_notes = conn.execute(
        "SELECT id FROM notes WHERE is_deleted = 1 AND deleted_at < ?", (cutoff,)
    ).fetchall()
    conn.close()
    for n in old_notes:
        permanent_delete_note(n["id"])


def get_trash_count():
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) as c FROM notes WHERE is_deleted = 1").fetchone()
    conn.close()
    return row["c"]


# --- Note Versions ---

def save_version(note_id, title, content):
    """Save a snapshot of the note."""
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO note_versions (note_id, title, content, saved_at) VALUES (?, ?, ?, ?)",
        (note_id, title, content, now),
    )
    conn.commit()
    conn.close()


def get_note_versions(note_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM note_versions WHERE note_id = ? ORDER BY saved_at DESC",
        (note_id,),
    ).fetchall()
    conn.close()
    return rows


def restore_version(note_id, version_id):
    """Restore a note from a saved version."""
    conn = get_connection()
    ver = conn.execute("SELECT * FROM note_versions WHERE id = ?", (version_id,)).fetchone()
    if ver:
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE notes SET title = ?, content = ?, updated_at = ? WHERE id = ?",
            (ver["title"], ver["content"], now, note_id),
        )
        conn.commit()
    conn.close()


# --- Encryption helpers ---

def set_note_encrypted(note_id, encrypted_content, is_encrypted=True):
    """Store encrypted content."""
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        "UPDATE notes SET content = ?, is_encrypted = ?, updated_at = ? WHERE id = ?",
        (encrypted_content, 1 if is_encrypted else 0, now, note_id),
    )
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


# --- Backup ---

def create_backup(dest_dir=None):
    """Create a backup of the database. Returns backup file path."""
    import shutil
    if dest_dir is None:
        dest_dir = BACKUP_DIR
    os.makedirs(dest_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"mynotes_backup_{timestamp}.db"
    backup_path = os.path.join(dest_dir, backup_name)
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def get_backups():
    """List available backups."""
    if not os.path.exists(BACKUP_DIR):
        return []
    backups = []
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if f.startswith("mynotes_backup_") and f.endswith(".db"):
            path = os.path.join(BACKUP_DIR, f)
            size = os.path.getsize(path)
            backups.append({"filename": f, "path": path, "size": size})
    return backups


# --- Export / Import (.mynote) ---

def export_note(note_id, dest_path):
    """Export a note as .mynote file (ZIP with JSON metadata + attachments)."""
    import zipfile
    import json

    note = get_note(note_id)
    if not note:
        raise ValueError("Nota non trovata")

    tags = get_note_tags(note_id)
    attachments = get_note_attachments(note_id)

    metadata = {
        "title": note["title"],
        "content": note["content"],
        "created_at": note["created_at"],
        "updated_at": note["updated_at"],
        "is_pinned": note["is_pinned"],
        "is_favorite": note["is_favorite"],
        "is_encrypted": note["is_encrypted"],
        "tags": [t["name"] for t in tags],
        "attachments": [a["original_name"] for a in attachments],
    }

    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("note.json", json.dumps(metadata, indent=2, ensure_ascii=False))
        for att in attachments:
            att_path = os.path.join(ATTACHMENTS_DIR, att["filename"])
            if os.path.exists(att_path):
                zf.write(att_path, f"attachments/{att['original_name']}")

    return dest_path


def import_note(source_path, category_id=None):
    """Import a .mynote file. Returns the new note ID."""
    import zipfile
    import json
    import shutil
    import uuid

    with zipfile.ZipFile(source_path, "r") as zf:
        meta = json.loads(zf.read("note.json"))

        note_id = add_note(meta["title"], meta.get("content", ""), category_id)

        # Restore flags
        conn = get_connection()
        conn.execute(
            "UPDATE notes SET is_pinned = ?, is_favorite = ?, is_encrypted = ? WHERE id = ?",
            (meta.get("is_pinned", 0), meta.get("is_favorite", 0),
             meta.get("is_encrypted", 0), note_id),
        )
        conn.commit()
        conn.close()

        # Restore tags
        for tag_name in meta.get("tags", []):
            tag_id = add_tag(tag_name)
            set_note_tags(note_id, [tag_id] + [t["id"] for t in get_note_tags(note_id)])

        # Restore attachments
        for name in zf.namelist():
            if name.startswith("attachments/"):
                original_name = os.path.basename(name)
                if not original_name:
                    continue
                ext = os.path.splitext(original_name)[1]
                filename = f"{uuid.uuid4().hex}{ext}"
                dest = os.path.join(ATTACHMENTS_DIR, filename)
                os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
                with zf.open(name) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                now = datetime.now().isoformat()
                conn = get_connection()
                conn.execute(
                    "INSERT INTO attachments (note_id, filename, original_name, added_at) VALUES (?, ?, ?, ?)",
                    (note_id, filename, original_name, now),
                )
                conn.commit()
                conn.close()

    return note_id
