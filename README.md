# MyNotes

App desktop per gestione note, appunti e documenti. Portabile, cross-platform, con database locale integrato.

## Funzionalita

- **Note con categorie e tag** - organizza le tue note come preferisci
- **Allegati** - allega qualsiasi file alle note
- **Screenshot e annotazioni** - cattura schermo, annota con frecce, rettangoli, testo e disegno libero
- **Checklist** - liste di cose da fare con checkbox cliccabili
- **Preferiti e pin** - fissa le note importanti in cima
- **Cestino** - elimina e ripristina note (pulizia automatica dopo 30 giorni)
- **Cronologia versioni** - visualizza e ripristina versioni precedenti
- **Crittografia** - proteggi le note con password (AES)
- **Esporta** - HTML, PDF, o formato `.mynote` per condivisione
- **Condivisione** - esporta/importa note come file `.mynote` (include allegati)
- **Backup** - locale automatico + Google Drive
- **Aggiornamento automatico** - controlla nuove versioni da GitHub
- **Portabile** - metti la cartella su una chiavetta USB e funziona ovunque

## Download

Scarica l'ultima versione dalla pagina [Releases](https://github.com/gamerhateyou/MyNotes/releases):

- **Windows** - `MyNotes-Windows.zip` → estrai ed esegui `MyNotes.exe`
- **Linux** - `MyNotes-Linux.tar.gz` → estrai ed esegui `./MyNotes`

Nessuna installazione richiesta. Entrambi sono portabili.

## Esegui da sorgente

```bash
# Requisiti: Python 3.10+ con tkinter
pip install -r requirements.txt
python main.py
```

### Requisiti di sistema

| | Windows | Linux |
|---|---------|-------|
| Python | 3.10+ | 3.10+ |
| tkinter | incluso | `sudo apt install python3-tk` / `sudo dnf install python3-tkinter` |
| Screenshot | funziona nativamente | `sudo apt install gnome-screenshot` o `sudo dnf install grim slurp` (Wayland) |

## Build eseguibile

```bash
pip install pyinstaller
python build_portable.py
```

L'eseguibile viene creato in `dist/MyNotes/`.

## Struttura progetto

```
MyNotes/
├── main.py              # Entry point
├── database.py          # SQLite data layer + export/import
├── gui.py               # Interfaccia Tkinter
├── dialogs.py           # Finestre di dialogo
├── annotator.py         # Tool annotazione immagini
├── image_utils.py       # Gestione immagini (PIL -> tk)
├── platform_utils.py    # Astrazione cross-platform
├── crypto_utils.py      # Crittografia AES
├── backup_utils.py      # Backup locale + Google Drive
├── updater.py           # Auto-aggiornamento da GitHub
├── version.py           # Versione e repo
├── build_portable.py    # Build con PyInstaller
├── requirements.txt     # Dipendenze Python
├── run.sh / run.bat     # Launcher portabili
└── .github/workflows/   # CI/CD GitHub Actions
```

## Licenza

MIT
