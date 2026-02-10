from __future__ import annotations

import os
import sqlite3
import stat
import sys
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any


class _Sentinel:
    """Sentinel value for explicit NULL."""

    def __repr__(self) -> str:
        return "<_UNSET>"


_UNSET = _Sentinel()

# Portable: tutto relativo alla cartella dell'app
if getattr(sys, "frozen", False):
    APP_DIR: str = os.path.dirname(sys.executable)
else:
    APP_DIR: str = os.path.dirname(os.path.abspath(__file__))  # type: ignore[no-redef]

DATA_DIR: str = os.path.join(APP_DIR, "data")
DB_PATH: str = os.path.join(DATA_DIR, "mynotes.db")
ATTACHMENTS_DIR: str = os.path.join(DATA_DIR, "attachments")
BACKUP_DIR: str = os.path.join(DATA_DIR, "backups")

TRASH_PURGE_DAYS: int = 30


@contextmanager
def _connect() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for safe database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA secure_delete = ON")
    try:
        yield conn
    finally:
        conn.close()


def get_connection() -> sqlite3.Connection:
    """Legacy helper - prefer _connect() context manager."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA secure_delete = ON")
    return conn


def _secure_dir(path: str) -> None:
    """Create directory with owner-only permissions (rwx------)."""
    os.makedirs(path, exist_ok=True)
    if sys.platform != "win32":
        os.chmod(path, stat.S_IRWXU)


def _secure_file(path: str) -> None:
    """Set file to owner-only permissions (rw-------)."""
    if os.path.exists(path) and sys.platform != "win32":
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def init_db() -> None:
    _secure_dir(DATA_DIR)
    _secure_dir(ATTACHMENTS_DIR)
    _secure_dir(BACKUP_DIR)
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                sort_order INTEGER DEFAULT 0
            );
            -- Category indices created in _migrate() to support existing DBs
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

            -- Indici per query frequenti
            CREATE INDEX IF NOT EXISTS idx_notes_category ON notes(category_id);
            CREATE INDEX IF NOT EXISTS idx_notes_deleted ON notes(is_deleted);
            CREATE INDEX IF NOT EXISTS idx_notes_pinned ON notes(is_pinned);
            CREATE INDEX IF NOT EXISTS idx_notes_favorite ON notes(is_favorite);
            CREATE INDEX IF NOT EXISTS idx_note_tags_tag ON note_tags(tag_id);
            CREATE INDEX IF NOT EXISTS idx_note_versions_note ON note_versions(note_id);
            CREATE INDEX IF NOT EXISTS idx_attachments_note ON attachments(note_id);

            CREATE TABLE IF NOT EXISTS pastebin_shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER NOT NULL,
                paste_key TEXT NOT NULL,
                paste_url TEXT NOT NULL,
                paste_title TEXT NOT NULL DEFAULT '',
                visibility INTEGER NOT NULL DEFAULT 1,
                expire_date TEXT NOT NULL DEFAULT 'N',
                shared_at TEXT NOT NULL,
                FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_pastebin_shares_note ON pastebin_shares(note_id);
        """)
        _migrate(conn)
        conn.commit()
    _secure_file(DB_PATH)
    purge_trash(TRASH_PURGE_DAYS)


def _migrate(conn: sqlite3.Connection) -> None:
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

    # Migrate categories table: add parent_id and sort_order
    cat_cols = {row[1] for row in conn.execute("PRAGMA table_info(categories)").fetchall()}
    if "parent_id" not in cat_cols:
        conn.execute("ALTER TABLE categories ADD COLUMN parent_id INTEGER REFERENCES categories(id) ON DELETE SET NULL")
    if "sort_order" not in cat_cols:
        conn.execute("ALTER TABLE categories ADD COLUMN sort_order INTEGER DEFAULT 0")
    # Drop old UNIQUE on name alone (if present) — sqlite can't drop constraints,
    # but the new idx_cat_name_parent index is created in init_db's executescript.
    # Ensure unique index exists for migrated DBs:
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_cat_name_parent ON categories(name, COALESCE(parent_id, 0))")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cat_parent ON categories(parent_id)")

    # Migrate pastebin_shares table for existing DBs
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "pastebin_shares" not in tables:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pastebin_shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER NOT NULL,
                paste_key TEXT NOT NULL,
                paste_url TEXT NOT NULL,
                paste_title TEXT NOT NULL DEFAULT '',
                visibility INTEGER NOT NULL DEFAULT 1,
                expire_date TEXT NOT NULL DEFAULT 'N',
                shared_at TEXT NOT NULL,
                FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pastebin_shares_note ON pastebin_shares(note_id)")


# --- Categories ---


def get_all_categories() -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM categories ORDER BY parent_id IS NOT NULL, parent_id, sort_order, name"
        ).fetchall()


def add_category(name: str, parent_id: int | None = None) -> int | None:
    with _connect() as conn:
        try:
            cur = conn.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (name, parent_id))
            conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None


def rename_category(cat_id: int, new_name: str) -> None:
    with _connect() as conn:
        try:
            conn.execute("UPDATE categories SET name = ? WHERE id = ?", (new_name, cat_id))
            conn.commit()
        except sqlite3.IntegrityError:
            pass


def delete_category(cat_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        conn.commit()


def get_descendant_category_ids(cat_id: int) -> list[int]:
    """BFS to find all descendant category IDs."""
    with _connect() as conn:
        queue = [cat_id]
        descendants: list[int] = []
        while queue:
            current = queue.pop(0)
            children = conn.execute("SELECT id FROM categories WHERE parent_id = ?", (current,)).fetchall()
            for child in children:
                descendants.append(child["id"])
                queue.append(child["id"])
        return descendants


def move_category(cat_id: int, new_parent_id: int | None) -> bool:
    """Move category to a new parent. Returns False if circular."""
    if new_parent_id == cat_id:
        return False
    if new_parent_id is not None:
        descendants = get_descendant_category_ids(cat_id)
        if new_parent_id in descendants:
            return False
    with _connect() as conn:
        conn.execute("UPDATE categories SET parent_id = ? WHERE id = ?", (new_parent_id, cat_id))
        conn.commit()
    return True


def delete_category_tree(cat_id: int) -> None:
    """Delete category + all descendants, soft-delete their notes."""
    descendants = get_descendant_category_ids(cat_id)
    all_ids = [cat_id] + descendants
    # Soft-delete all notes in these categories
    with _connect() as conn:
        if all_ids:
            placeholders = ",".join("?" * len(all_ids))
            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE notes SET is_deleted = 1, deleted_at = ?"
                f" WHERE category_id IN ({placeholders}) AND is_deleted = 0",
                [now, *all_ids],
            )
            # Delete categories (children first to avoid FK issues)
            for cid in reversed(all_ids):
                conn.execute("DELETE FROM categories WHERE id = ?", (cid,))
        conn.commit()


def promote_children(cat_id: int) -> None:
    """Move children of cat_id to cat_id's parent."""
    with _connect() as conn:
        cat = conn.execute("SELECT parent_id FROM categories WHERE id = ?", (cat_id,)).fetchone()
        if not cat:
            return
        parent_id = cat["parent_id"]
        conn.execute("UPDATE categories SET parent_id = ? WHERE parent_id = ?", (parent_id, cat_id))
        conn.commit()


def get_category_path(cat_id: int) -> list[sqlite3.Row]:
    """Return path from root to this category (list of Row)."""
    with _connect() as conn:
        path: list[sqlite3.Row] = []
        current_id: int | None = cat_id
        visited: set[int] = set()
        while current_id is not None and current_id not in visited:
            visited.add(current_id)
            row = conn.execute("SELECT * FROM categories WHERE id = ?", (current_id,)).fetchone()
            if not row:
                break
            path.append(row)
            current_id = row["parent_id"]
        path.reverse()
        return path


# --- Notes ---


def get_all_notes(
    category_id: int | None = None,
    tag_id: int | None = None,
    search_query: str | None = None,
    show_deleted: bool = False,
    favorites_only: bool = False,
) -> list[sqlite3.Row]:
    with _connect() as conn:
        query = "SELECT DISTINCT n.* FROM notes n"
        joins = []
        conditions = []
        params: list[int | str] = []

        conditions.append("n.is_deleted = 1" if show_deleted else "n.is_deleted = 0")

        if favorites_only:
            conditions.append("n.is_favorite = 1")
        if tag_id is not None:
            joins.append("JOIN note_tags nt ON n.id = nt.note_id")
            conditions.append("nt.tag_id = ?")
            params.append(tag_id)
        if category_id is not None:
            descendant_ids = get_descendant_category_ids(category_id)
            all_cat_ids = [category_id] + descendant_ids
            cat_placeholders = ",".join("?" * len(all_cat_ids))
            conditions.append(f"n.category_id IN ({cat_placeholders})")
            params.extend(all_cat_ids)
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


def get_note(note_id: int) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()  # type: ignore[no-any-return]


def add_note(title: str, content: str = "", category_id: int | None = None) -> int:
    now = datetime.now().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO notes (title, content, category_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (title, content, category_id, now, now),
        )
        note_id = cur.lastrowid
        conn.commit()
        assert note_id is not None
        return note_id


def update_note(
    note_id: int, title: str | None = None, content: str | None = None, category_id: int | _Sentinel | None = None
) -> None:
    with _connect() as conn:
        note = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if not note:
            return
        now = datetime.now().isoformat()
        # _UNSET sentinel means "set to NULL explicitly"
        if category_id is _UNSET:
            effective_category = None
        elif category_id is not None:
            effective_category = category_id
        else:
            effective_category = note["category_id"]
        conn.execute(
            "UPDATE notes SET title = ?, content = ?, category_id = ?, updated_at = ? WHERE id = ?",
            (
                title if title is not None else note["title"],
                content if content is not None else note["content"],
                effective_category,
                now,
                note_id,
            ),
        )
        conn.commit()


def toggle_pin(note_id: int) -> None:
    with _connect() as conn:
        note = conn.execute("SELECT is_pinned FROM notes WHERE id = ?", (note_id,)).fetchone()
        if note:
            conn.execute("UPDATE notes SET is_pinned = ? WHERE id = ?", (0 if note["is_pinned"] else 1, note_id))
            conn.commit()


def toggle_favorite(note_id: int) -> None:
    with _connect() as conn:
        note = conn.execute("SELECT is_favorite FROM notes WHERE id = ?", (note_id,)).fetchone()
        if note:
            conn.execute("UPDATE notes SET is_favorite = ? WHERE id = ?", (0 if note["is_favorite"] else 1, note_id))
            conn.commit()


# --- Trash ---


def soft_delete_note(note_id: int) -> None:
    now = datetime.now().isoformat()
    with _connect() as conn:
        conn.execute("UPDATE notes SET is_deleted = 1, deleted_at = ? WHERE id = ?", (now, note_id))
        conn.commit()


def restore_note(note_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE notes SET is_deleted = 0, deleted_at = NULL WHERE id = ?", (note_id,))
        conn.commit()


def permanent_delete_note(note_id: int) -> None:
    with _connect() as conn:
        attachments = conn.execute("SELECT filename FROM attachments WHERE note_id = ?", (note_id,)).fetchall()
        for att in attachments:
            path = os.path.join(ATTACHMENTS_DIR, att["filename"])
            if os.path.exists(path):
                os.remove(path)
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()


def purge_trash(days: int = TRASH_PURGE_DAYS) -> None:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    with _connect() as conn:
        old_notes = conn.execute(
            "SELECT n.id, a.filename FROM notes n "
            "LEFT JOIN attachments a ON a.note_id = n.id "
            "WHERE n.is_deleted = 1 AND n.deleted_at < ?",
            (cutoff,),
        ).fetchall()
        # Cancella file allegati
        for row in old_notes:
            if row["filename"]:
                path = os.path.join(ATTACHMENTS_DIR, row["filename"])
                if os.path.exists(path):
                    os.remove(path)
        # Cancella note (CASCADE elimina note_tags, attachments, versions)
        note_ids = list({row["id"] for row in old_notes})
        if note_ids:
            placeholders = ",".join("?" * len(note_ids))
            conn.execute(f"DELETE FROM notes WHERE id IN ({placeholders})", note_ids)
            conn.commit()


def soft_delete_notes(note_ids: list[int]) -> None:
    if not note_ids:
        return
    now = datetime.now().isoformat()
    with _connect() as conn:
        placeholders = ",".join("?" * len(note_ids))
        conn.execute(
            f"UPDATE notes SET is_deleted = 1, deleted_at = ? WHERE id IN ({placeholders})",
            [now] + list(note_ids),
        )
        conn.commit()


def permanent_delete_notes(note_ids: list[int]) -> None:
    if not note_ids:
        return
    with _connect() as conn:
        placeholders = ",".join("?" * len(note_ids))
        attachments = conn.execute(
            f"SELECT filename FROM attachments WHERE note_id IN ({placeholders})",
            list(note_ids),
        ).fetchall()
        for att in attachments:
            path = os.path.join(ATTACHMENTS_DIR, att["filename"])
            if os.path.exists(path):
                os.remove(path)
        conn.execute(f"DELETE FROM notes WHERE id IN ({placeholders})", list(note_ids))
        conn.commit()


def restore_notes(note_ids: list[int]) -> None:
    if not note_ids:
        return
    with _connect() as conn:
        placeholders = ",".join("?" * len(note_ids))
        conn.execute(
            f"UPDATE notes SET is_deleted = 0, deleted_at = NULL WHERE id IN ({placeholders})",
            list(note_ids),
        )
        conn.commit()


def set_pinned_notes(note_ids: list[int], value: bool) -> None:
    if not note_ids:
        return
    with _connect() as conn:
        placeholders = ",".join("?" * len(note_ids))
        conn.execute(
            f"UPDATE notes SET is_pinned = ? WHERE id IN ({placeholders})",
            [1 if value else 0] + list(note_ids),
        )
        conn.commit()


def set_favorite_notes(note_ids: list[int], value: bool) -> None:
    if not note_ids:
        return
    with _connect() as conn:
        placeholders = ",".join("?" * len(note_ids))
        conn.execute(
            f"UPDATE notes SET is_favorite = ? WHERE id IN ({placeholders})",
            [1 if value else 0] + list(note_ids),
        )
        conn.commit()


def move_notes_to_category(note_ids: list[int], category_id: int | _Sentinel | None) -> None:
    if not note_ids:
        return
    effective = None if category_id is _UNSET else category_id
    with _connect() as conn:
        placeholders = ",".join("?" * len(note_ids))
        conn.execute(
            f"UPDATE notes SET category_id = ? WHERE id IN ({placeholders})",
            [effective] + list(note_ids),
        )
        conn.commit()


def get_note_ids_by_category(cat_id: int, include_descendants: bool = False) -> list[int]:
    all_ids = [cat_id]
    if include_descendants:
        all_ids += get_descendant_category_ids(cat_id)
    with _connect() as conn:
        placeholders = ",".join("?" * len(all_ids))
        rows = conn.execute(
            f"SELECT id FROM notes WHERE category_id IN ({placeholders}) AND is_deleted = 0", all_ids
        ).fetchall()
        return [r["id"] for r in rows]


def delete_category_with_notes(cat_id: int) -> None:
    note_ids = get_note_ids_by_category(cat_id)
    if note_ids:
        soft_delete_notes(note_ids)
    delete_category(cat_id)


def get_trash_count() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) as c FROM notes WHERE is_deleted = 1").fetchone()
        return row["c"]  # type: ignore[no-any-return]


# --- Note Versions ---

MAX_VERSIONS_PER_NOTE: int = 50


def save_version(note_id: int, title: str, content: str) -> None:
    now = datetime.now().isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO note_versions (note_id, title, content, saved_at) VALUES (?, ?, ?, ?)",
            (note_id, title, content, now),
        )
        # Mantieni solo le ultime MAX_VERSIONS_PER_NOTE versioni
        conn.execute(
            "DELETE FROM note_versions WHERE note_id = ? AND id NOT IN "
            "(SELECT id FROM note_versions WHERE note_id = ? ORDER BY saved_at DESC LIMIT ?)",
            (note_id, note_id, MAX_VERSIONS_PER_NOTE),
        )
        conn.commit()


def get_note_versions(note_id: int) -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM note_versions WHERE note_id = ? ORDER BY saved_at DESC",
            (note_id,),
        ).fetchall()


def restore_version(note_id: int, version_id: int) -> None:
    with _connect() as conn:
        ver = conn.execute("SELECT * FROM note_versions WHERE id = ?", (version_id,)).fetchone()
        if ver:
            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE notes SET title = ?, content = ?, updated_at = ? WHERE id = ?",
                (ver["title"], ver["content"], now, note_id),
            )
            conn.commit()


def delete_note_versions(note_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM note_versions WHERE note_id = ?", (note_id,))
        conn.commit()


# --- Encryption helpers ---


def set_note_encrypted(note_id: int, encrypted_content: str, is_encrypted: bool = True) -> None:
    now = datetime.now().isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE notes SET content = ?, is_encrypted = ?, updated_at = ? WHERE id = ?",
            (encrypted_content, 1 if is_encrypted else 0, now, note_id),
        )
        conn.commit()


# --- Tags ---


def get_all_tags() -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute("SELECT * FROM tags ORDER BY name").fetchall()


def add_tag(name: str) -> int:
    with _connect() as conn:
        try:
            cur = conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
            tag_id = cur.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
            tag_id = row["id"] if row else 0
        assert tag_id is not None
        return int(tag_id)


def delete_tag(tag_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        conn.commit()


def get_note_tags(note_id: int) -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT t.* FROM tags t JOIN note_tags nt ON t.id = nt.tag_id WHERE nt.note_id = ? ORDER BY t.name",
            (note_id,),
        ).fetchall()


def set_note_tags(note_id: int, tag_ids: list[int]) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
        for tid in tag_ids:
            conn.execute("INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)", (note_id, tid))
        conn.commit()


# --- Attachments ---


def get_note_attachments(note_id: int) -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute("SELECT * FROM attachments WHERE note_id = ? ORDER BY added_at DESC", (note_id,)).fetchall()


def add_attachment(note_id: int, source_path: str) -> str:
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


def delete_attachment(att_id: int) -> None:
    with _connect() as conn:
        att = conn.execute("SELECT filename FROM attachments WHERE id = ?", (att_id,)).fetchone()
        if att:
            path = os.path.join(ATTACHMENTS_DIR, att["filename"])
            if os.path.exists(path):
                os.remove(path)
            conn.execute("DELETE FROM attachments WHERE id = ?", (att_id,))
            conn.commit()


# --- Backup ---


def create_backup(dest_dir: str | None = None) -> str:
    import shutil

    if dest_dir is None:
        dest_dir = BACKUP_DIR
    os.makedirs(dest_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"mynotes_backup_{timestamp}.db"
    backup_path = os.path.join(dest_dir, backup_name)
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def get_backups(backup_dir: str | None = None) -> list[dict[str, Any]]:
    bdir = backup_dir or BACKUP_DIR
    if not os.path.exists(bdir):
        return []
    backups = []
    for f in sorted(os.listdir(bdir), reverse=True):
        if f.startswith("mynotes_backup_") and (f.endswith(".db") or f.endswith(".db.enc")):
            path = os.path.join(bdir, f)
            size = os.path.getsize(path)
            # Parse data dal filename
            try:
                name = f.replace(".db.enc", ".db")
                ts = datetime.strptime(name, "mynotes_backup_%Y%m%d_%H%M%S.db")
                date_str = ts.strftime("%d/%m/%Y %H:%M:%S")
            except ValueError:
                date_str = ""
            backups.append(
                {
                    "filename": f,
                    "path": path,
                    "size": size,
                    "date_str": date_str,
                    "encrypted": f.endswith(".db.enc"),
                }
            )
    return backups


# --- Export / Import (.mynote) ---


def _ensure_category_path(path: list[str]) -> int | None:
    """Ensure category hierarchy exists and return leaf category ID."""
    parent_id: int | None = None
    with _connect() as conn:
        for name in path:
            row = conn.execute(
                "SELECT id FROM categories WHERE name = ? AND COALESCE(parent_id, 0) = ?",
                (name, parent_id or 0),
            ).fetchone()
            if row:
                parent_id = row["id"]
            else:
                cur = conn.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (name, parent_id))
                conn.commit()
                parent_id = cur.lastrowid
    return parent_id


def export_note(note_id: int, dest_path: str) -> str:
    import json
    import zipfile

    note = get_note(note_id)
    if not note:
        raise ValueError("Nota non trovata")

    tags = get_note_tags(note_id)
    attachments = get_note_attachments(note_id)

    # Build category path for hierarchical export
    category_path: list[str] = []
    if note["category_id"]:
        category_path = [r["name"] for r in get_category_path(note["category_id"])]

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
        "category_path": category_path,
    }

    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("note.json", json.dumps(metadata, indent=2, ensure_ascii=False))
        for att in attachments:
            att_path = os.path.join(ATTACHMENTS_DIR, att["filename"])
            if os.path.exists(att_path):
                zf.write(att_path, f"attachments/{att['original_name']}")

    return dest_path


def import_note(source_path: str, category_id: int | None = None) -> int:
    import json
    import shutil
    import uuid
    import zipfile

    with zipfile.ZipFile(source_path, "r") as zf:
        meta = json.loads(zf.read("note.json"))

        # Recreate category hierarchy from category_path if present
        effective_category_id = category_id
        cat_path = meta.get("category_path", [])
        if cat_path and category_id is None:
            effective_category_id = _ensure_category_path(cat_path)

        note_id = add_note(meta["title"], meta.get("content", ""), effective_category_id)

        # Restore flags + tags in single connection
        with _connect() as conn:
            conn.execute(
                "UPDATE notes SET is_pinned = ?, is_favorite = ?, is_encrypted = ? WHERE id = ?",
                (meta.get("is_pinned", 0), meta.get("is_favorite", 0), meta.get("is_encrypted", 0), note_id),
            )
            conn.commit()

        tag_ids = [add_tag(name) for name in meta.get("tags", [])]
        if tag_ids:
            set_note_tags(note_id, tag_ids)

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


# --- Pastebin Shares ---


def add_pastebin_share(
    note_id: int,
    paste_key: str,
    paste_url: str,
    paste_title: str,
    visibility: int,
    expire_date: str,
) -> int:
    now = datetime.now().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO pastebin_shares"
            " (note_id, paste_key, paste_url, paste_title, visibility, expire_date, shared_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (note_id, paste_key, paste_url, paste_title, visibility, expire_date, now),
        )
        conn.commit()
        share_id = cur.lastrowid
        assert share_id is not None
        return share_id


def get_pastebin_shares(note_id: int | None = None) -> list[sqlite3.Row]:
    with _connect() as conn:
        if note_id is not None:
            return conn.execute(
                "SELECT ps.*, n.title AS note_title FROM pastebin_shares ps"
                " JOIN notes n ON ps.note_id = n.id WHERE ps.note_id = ? ORDER BY ps.shared_at DESC",
                (note_id,),
            ).fetchall()
        return conn.execute(
            "SELECT ps.*, n.title AS note_title FROM pastebin_shares ps"
            " JOIN notes n ON ps.note_id = n.id ORDER BY ps.shared_at DESC"
        ).fetchall()


def delete_pastebin_share(share_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM pastebin_shares WHERE id = ?", (share_id,))
        conn.commit()
