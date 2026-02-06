#!/bin/bash
# MyNotes - Launcher Linux
# Avvia l'app dalla cartella corrente (portabile da chiavetta USB)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Cerca Python3
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "ERRORE: Python non trovato!"
    echo "Installa Python 3: sudo dnf install python3 python3-tkinter"
    echo "Oppure: sudo apt install python3 python3-tk"
    read -p "Premi invio per chiudere..."
    exit 1
fi

# Verifica tkinter
$PYTHON -c "import tkinter" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "ERRORE: tkinter non installato!"
    echo "Fedora/RHEL: sudo dnf install python3-tkinter"
    echo "Ubuntu/Debian: sudo apt install python3-tk"
    echo "Arch: sudo pacman -S tk"
    read -p "Premi invio per chiudere..."
    exit 1
fi

# Installa Pillow se manca (nella cartella utente)
$PYTHON -c "from PIL import Image" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installazione Pillow..."
    $PYTHON -m pip install --user Pillow 2>/dev/null || pip3 install --user Pillow 2>/dev/null
fi

# Avvia
exec $PYTHON "$SCRIPT_DIR/main.py"
