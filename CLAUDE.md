# MyNotes

## Architettura
- App desktop Python/Tkinter con SQLite locale, portabile e cross-platform (Windows + Linux)
- Pattern MVC leggero: `database.py` (model), `gui.py` (view/controller), `dialogs.py` (dialog views)
- `platform_utils.py` astrae tutte le differenze OS (file opening, screenshot, fonts)
- `image_utils.py` converte PIL -> PNG base64 -> tk.PhotoImage (workaround per ImageTk mancante)
- `crypto_utils.py` crittografia AES con PBKDF2 (Fernet se disponibile, fallback XOR+HMAC)
- `backup_utils.py` backup locale + Google Drive con OAuth integrato nella GUI
- `updater.py` auto-aggiornamento da GitHub Releases, `version.py` contiene VERSION e GITHUB_REPO
- Dati in `data/` (db + allegati + token + settings) accanto all'eseguibile, MAI sovrascritta durante update
- Export/import note come `.mynote` (ZIP con JSON metadata + allegati)

## Comandi
- `python3 main.py` - avvia l'app
- `./run.sh` / `run.bat` - launcher portabili che verificano dipendenze
- `python build_portable.py` - build eseguibile standalone con PyInstaller
- `git tag vX.Y.Z && git push origin vX.Y.Z` - triggera GitHub Actions build + release

## Quirk ambiente
- Fedora/Wayland: `ImageTk` non disponibile, usare pipeline PIL->base64->tk.PhotoImage
- Screenshot Wayland: servono `grim` + `slurp` (`sudo dnf install grim slurp`)
- Font Fedora: AdwaitaSans in `/usr/share/fonts/adwaita-sans-fonts/`
- tkinter va installato separatamente: `sudo dnf install python3-tkinter`

## Stile codice
- Interfaccia in italiano (label, messaggi, menu)
- Nomi variabili/funzioni in inglese con prefisso `_` per metodi privati
- Dipendenze: Pillow, reportlab, google-api-python-client, google-auth-oauthlib (tutte in requirements.txt)
- Tutti i path relativi a APP_DIR (portabilita chiavetta USB)
- Google Drive: OAuth credentials embedded in backup_utils.py, utente clicca solo "Accedi con Google"

## Build & Deploy
- GitHub Actions workflow in `.github/workflows/build.yml` builda Linux + Windows
- Release automatica su push tag `v*`
- GITHUB_REPO in `version.py` impostato a "gamerhateyou/MyNotes"
- PyInstaller include tutte le librerie Google come hidden imports
