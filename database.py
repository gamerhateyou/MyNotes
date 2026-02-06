import sqlite3
import os
import sys
from contextlib import contextmanager
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

TRASH_PURGE_DAYS = 30


@contextmanager
def _connect():
    """Context manager for safe database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def get_connection():
    """Legacy helper - prefer _connect() context manager."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with _connect() as conn:
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
        _migrate(conn)
        conn.commit()
    purge_trash(TRASH_PURGE_DAYS)


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
    with _connect() as conn:
        return conn.execute("SELECT * FROM categories ORDER BY name").fetchall()


def add_category(name):
    with _connect() as conn:
        try:
            conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            conn.commit()
        except sqlite3.IntegrityError:
            pass


def rename_category(cat_id, new_name):
    with _connect() as conn:
        try:
            conn.execute("UPDATE categories SET name = ? WHERE id = ?", (new_name, cat_id))
            conn.commit()
        except sqlite3.IntegrityError:
            pass


def delete_category(cat_id):
    with _connect() as conn:
        conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        conn.commit()


# --- Notes ---

def get_all_notes(category_id=None, tag_id=None, search_query=None,
                  show_deleted=False, favorites_only=False):
    with _connect() as conn:
        query = "SELECT DISTINCT n.* FROM notes n"
        joins = []
        conditions = []
        params = []

        conditions.append("n.is_deleted = 1" if show_deleted else "n.is_deleted = 0")

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
        query += " ORDER BY n.is_pinned DESC, n.updated_at DESC"

        return conn.execute(query, params).fetchall()


def get_note(note_id):
    with _connect() as conn:
        return conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()


def add_note(title, content="", category_id=None):
    now = datetime.now().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO notes (title, content, category_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (title, content, category_id, now, now),
        )
        note_id = cur.lastrowid
        conn.commit()
        return note_id


def update_note(note_id, title=None, content=None, category_id=None):
    with _connect() as conn:
        note = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if not note:
            return
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE notes SET title = ?, content = ?, category_id = ?, updated_at = ? WHERE id = ?",
            (
                title if title is not None else note["title"],
                content if content is not None else note["content"],
                category_id if category_id is not None else note["category_id"],
                now, note_id,
            ),
        )
        conn.commit()


def toggle_pin(note_id):
    with _connect() as conn:
        note = conn.execute("SELECT is_pinned FROM notes WHERE id = ?", (note_id,)).fetchone()
        if note:
            conn.execute("UPDATE notes SET is_pinned = ? WHERE id = ?",
                         (0 if note["is_pinned"] else 1, note_id))
            conn.commit()


def toggle_favorite(note_id):
    with _connect() as conn:
        note = conn.execute("SELECT is_favorite FROM notes WHERE id = ?", (note_id,)).fetchone()
        if note:
            conn.execute("UPDATE notes SET is_favorite = ? WHERE id = ?",
                         (0 if note["is_favorite"] else 1, note_id))
            conn.commit()


# --- Trash ---

def soft_delete_note(note_id):
    now = datetime.now().isoformat()
    with _connect() as conn:
        conn.execute("UPDATE notes SET is_deleted = 1, deleted_at = ? WHERE id = ?", (now, note_id))
        conn.commit()


def restore_note(note_id):
    with _connect() as conn:
        conn.execute("UPDATE notes SET is_deleted = 0, deleted_at = NULL WHERE id = ?", (note_id,))
        conn.commit()


def permanent_delete_note(note_id):
    with _connect() as conn:
        attachments = conn.execute(
            "SELECT filename FROM attachments WHERE note_id = ?", (note_id,)
        ).fetchall()
        for att in attachments:
            path = os.path.join(ATTACHMENTS_DIR, att["filename"])
            if os.path.exists(path):
                os.remove(path)
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()


def purge_trash(days=TRASH_PURGE_DAYS):
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    with _connect() as conn:
        old_notes = conn.execute(
            "SELECT id FROM notes WHERE is_deleted = 1 AND deleted_at < ?", (cutoff,)
        ).fetchall()
    for n in old_notes:
        permanent_delete_note(n["id"])


def get_trash_count():
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) as c FROM notes WHERE is_deleted = 1").fetchone()
        return row["c"]


# --- Note Versions ---

def save_version(note_id, title, content):
    now = datetime.now().isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO note_versions (note_id, title, content, saved_at) VALUES (?, ?, ?, ?)",
            (note_id, title, content, now),
        )
        conn.commit()


def get_note_versions(note_id):
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM note_versions WHERE note_id = ? ORDER BY saved_at DESC",
            (note_id,),
        ).fetchall()


def restore_version(note_id, version_id):
    with _connect() as conn:
        ver = conn.execute("SELECT * FROM note_versions WHERE id = ?", (version_id,)).fetchone()
        if ver:
            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE notes SET title = ?, content = ?, updated_at = ? WHERE id = ?",
                (ver["title"], ver["content"], now, note_id),
            )
            conn.commit()


# --- Encryption helpers ---

def set_note_encrypted(note_id, encrypted_content, is_encrypted=True):
    now = datetime.now().isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE notes SET content = ?, is_encrypted = ?, updated_at = ? WHERE id = ?",
            (encrypted_content, 1 if is_encrypted else 0, now, note_id),
        )
        conn.commit()


# --- Tags ---

def get_all_tags():
    with _connect() as conn:
        return conn.execute("SELECT * FROM tags ORDER BY name").fetchall()


def add_tag(name):
    with _connect() as conn:
        try:
            cur = conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
            tag_id = cur.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()["id"]
        return tag_id


def delete_tag(tag_id):
    with _connect() as conn:
        conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        conn.commit()


def get_note_tags(note_id):
    with _connect() as conn:
        return conn.execute(
            "SELECT t.* FROM tags t JOIN note_tags nt ON t.id = nt.tag_id WHERE nt.note_id = ? ORDER BY t.name",
            (note_id,),
        ).fetchall()


def set_note_tags(note_id, tag_ids):
    with _connect() as conn:
        conn.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
        for tid in tag_ids:
            conn.execute("INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)", (note_id, tid))
        conn.commit()


# --- Attachments ---

def get_note_attachments(note_id):
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM attachments WHERE note_id = ? ORDER BY added_at DESC", (note_id,)
        ).fetchall()


def add_attachment(note_id, source_path):
    import shutil
    import uuid

    original_name = os.path.basename(source_path)
    ext = os.path.splitext(original_name)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(ATTACHMENTS_DIR, filename)
    shutil.copy2(source_path, dest)

    now = datetime.now().isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO attachments (note_id, filename, original_name, added_at) VALUES (?, ?, ?, ?)",
            (note_id, filename, original_name, now),
        )
        conn.commit()
    return filename


def delete_attachment(att_id):
    with _connect() as conn:
        att = conn.execute("SELECT filename FROM attachments WHERE id = ?", (att_id,)).fetchone()
        if att:
            path = os.path.join(ATTACHMENTS_DIR, att["filename"])
            if os.path.exists(path):
                os.remove(path)
            conn.execute("DELETE FROM attachments WHERE id = ?", (att_id,))
            conn.commit()


# --- Backup ---

def create_backup(dest_dir=None):
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
    import zipfile
    import json
    import shutil
    import uuid

    with zipfile.ZipFile(source_path, "r") as zf:
        meta = json.loads(zf.read("note.json"))
        note_id = add_note(meta["title"], meta.get("content", ""), category_id)

        # Restore flags + tags in single connection
        with _connect() as conn:
            conn.execute(
                "UPDATE notes SET is_pinned = ?, is_favorite = ?, is_encrypted = ? WHERE id = ?",
                (meta.get("is_pinned", 0), meta.get("is_favorite", 0),
                 meta.get("is_encrypted", 0), note_id),
            )
            conn.commit()

        for tag_name in meta.get("tags", []):
            tag_id = add_tag(tag_name)
            set_note_tags(note_id, [tag_id] + [t["id"] for t in get_note_tags(note_id)])

        # Restore attachments
        with _connect() as conn:
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
                    conn.execute(
                        "INSERT INTO attachments (note_id, filename, original_name, added_at) VALUES (?, ?, ?, ?)",
                        (note_id, filename, original_name, now),
                    )
            conn.commit()

    return note_id
