# MyNotes

## Architettura
- App desktop Python/Tkinter con SQLite locale, portabile e cross-platform (Windows + Linux)
- Pattern MVC leggero: `database.py` (model), `gui.py` (view/controller), `dialogs.py` (dialog views)
- `platform_utils.py` astrae tutte le differenze OS (file opening, screenshot, fonts)
- `image_utils.py` converte PIL -> PNG base64 -> tk.PhotoImage (workaround per ImageTk mancante)
- `updater.py` auto-aggiornamento da GitHub Releases, `version.py` contiene VERSION e GITHUB_REPO
- Dati in `data/` (db + allegati) accanto all'eseguibile, MAI sovrascritta durante update

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
- Unica dipendenza esterna: Pillow (requirements.txt)
- Tutti i path relativi a APP_DIR (portabilità chiavetta USB)

## Build & Deploy
- GitHub Actions workflow in `.github/workflows/build.yml` builda Linux + Windows
- Release automatica su push tag `v*`
- GITHUB_REPO in `version.py` impostato a "gamerhateyou/MyNotes"
