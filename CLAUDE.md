# MyNotes

## Architettura
- App desktop Python/PySide6 con SQLite locale, portabile e cross-platform (Windows + Linux)
- Pattern MVC: `database.py` (model con context manager `_connect()`), `gui/` package (controller per area), `dialogs/` package (dialog views)
- `gui/`: `__init__.py` (app principale `MyNotesApp`), `constants.py`, `layout.py`, `menu.py`, `widgets.py`, `formatting.py`, `note_controller.py`, `export_controller.py`, `media_controller.py`, `backup_controller.py`, `update_controller.py`, `note_window.py`
- `dialogs/`: `category.py`, `tags.py`, `attachments.py`, `history.py`, `audio.py`, `password.py`, `backup.py`
- `platform_utils.py` astrae tutte le differenze OS (file opening, screenshot, fonts); `_find_tool()` cerca binari in PATH + path standard
- `image_utils.py` converte PIL -> QPixmap via PNG buffer
- `crypto_utils.py` crittografia AES con PBKDF2 (Fernet via cryptography)
- `backup_utils.py` backup locale + Google Drive (re-export da `gdrive_utils.py`) con OAuth integrato nella GUI
- `updater.py` auto-aggiornamento da GitHub Releases, `version.py` contiene VERSION e GITHUB_REPO
- `_types.py` type alias condivisi (`NoteRow`, `CategoryRow`, `ProgressCallback`, etc.)
- `annotator.py` tool di annotazione immagini con QGraphicsView
- Dati in `data/` (db + allegati + token + settings) accanto all'eseguibile, MAI sovrascritta durante update
- Export/import note come `.mynote` (ZIP con JSON metadata + allegati + `category_path` gerarchico)

## Categorie gerarchiche
- DB: `categories` ha `parent_id` (FK self-ref) e `sort_order`; UNIQUE su `(name, COALESCE(parent_id, 0))`
- Sidebar: `QTreeWidget` (`app.cat_tree`), NON QListWidget; items speciali usano UserRole `"__all__"`, `"__favorites__"`, `"__trash__"` (stringhe), categorie utente usano `int` (cat_id)
- `app._cat_items: dict[int, QTreeWidgetItem]` mappa cat_id → item per selezione/reload
- `db.get_descendant_category_ids()` BFS per filtrare note di tutta la gerarchia
- `db.move_category()` con check anti-circolarita; `db.delete_category_tree()` elimina ricorsivamente
- Eliminazione con figli: dialog 3 opzioni (elimina tutto / promuovi figli / annulla)

## Comandi
- `python3 main.py` - avvia l'app
- `python build_portable.py` - build eseguibile standalone con PyInstaller
- `ruff check .` - lint (zero errori richiesti)
- `ruff format --check .` - verifica formattazione (zero diff richiesti)
- `mypy .` - type check strict (zero errori richiesti)
- `git tag vX.Y.Z && git push origin vX.Y.Z` - triggera GitHub Actions build + release

## Quality Gates (CI)
- `.github/workflows/build.yml` ha job `quality` che gira su ogni push/PR a `main`
- Il job `quality` esegue: `ruff check .`, `ruff format --check .`, `mypy .`
- Il job `build` richiede `quality` e gira solo su tag push (`v*`) o workflow_dispatch
- Configurazione ruff e mypy in `pyproject.toml`
- Dev dependencies in `requirements-dev.txt` (include ruff e mypy)

## Type Safety
- Tutti i 34 file Python hanno `from __future__ import annotations`
- Tutte le ~334 funzioni sono annotate (parametri + return type)
- mypy strict mode abilitato (`disallow_untyped_defs`, `warn_return_any`, etc.)
- PySide6 enum access fully-qualified (es. `Qt.Key.Key_Escape`, `QMessageBox.StandardButton.Yes`)
- Pattern `TYPE_CHECKING` per evitare circular import tra gui controllers e `MyNotesApp`
- Sentinel tipizzato: `class _Sentinel` in `database.py` per `_UNSET`
- Librerie senza stubs ignorate via `[[tool.mypy.overrides]]`: qdarktheme, sounddevice, reportlab, google-*, numpy, PIL, certifi

## Quirk ambiente
- Fedora/Wayland: Screenshot servono `grim` + `slurp` (`sudo dnf install grim slurp`)
- Font Fedora: AdwaitaSans in `/usr/share/fonts/adwaita-sans-fonts/`
- PySide6 su Linux richiede `libegl1` e `libportaudio2` per sounddevice

## Stile codice
- Interfaccia in italiano (label, messaggi, menu)
- Nomi variabili/funzioni in inglese con prefisso `_` per metodi privati
- ruff rules: E/W/F/I/UP/B/SIM/ANN, line-length 120, target py312
- Dipendenze pinnate con `==` in `requirements.txt`
- Tutti i path relativi a APP_DIR (portabilita chiavetta USB)
- Google Drive: OAuth credentials iniettati al build da env vars, utente clicca solo "Accedi con Google"
- Versioning: bump minor per nuove feature, patch per bugfix; aggiornare `version.py` prima del commit
- Commit + release: `ruff check . && ruff format --check . && mypy .` PRIMA del commit, poi `git tag vX.Y.Z && git push origin main vX.Y.Z`

## Gotcha critici
- PySide6 widget: editor usa `QPlainTextEdit`, non Tkinter Text
- `save_current()` non deve leggere contenuto editor se nota crittografata (placeholder)
- Updater: mai trattare errori di rete come "gia aggiornato" - lanciare ConnectionError
- Release: NON eliminare release vecchie valide, tenerle per chi ha versioni precedenti
- PyInstaller: usare `--hidden-import` per moduli Python, MAI `--add-data` per file .py
- `os.startfile` solo Windows: richiede `# type: ignore[attr-defined]`
- `self.result` nei dialog shadowa `QDialog.result()`: richiede `# type: ignore[assignment]`
- `raise` in `except`: sempre usare `from e` o `from None` (regola B904)
- PyInstaller `--windowed` su Linux: `PATH` puo' essere vuoto, usare `_find_tool()` in `platform_utils.py` (non `shutil.which()` diretto)
- mypy: `[now] + all_ids` con tipi misti (`str + list[int]`) fallisce — usare `[now, *all_ids]` (unpacking)
- Sidebar: MAI usare indici riga per identificare categorie — leggere `item.data(0, Qt.ItemDataRole.UserRole)`

## Build & Deploy
- GitHub Actions workflow in `.github/workflows/build.yml` builda Linux + Windows
- Job `quality` blocca la build se ruff o mypy falliscono
- Release automatica su push tag `v*`
- GITHUB_REPO in `version.py` impostato a "gamerhateyou/MyNotes"
- PyInstaller include tutte le librerie Google come hidden imports
