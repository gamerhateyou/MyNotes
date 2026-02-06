@echo off
REM MyNotes - Launcher Windows
REM Avvia l'app dalla cartella corrente (portabile da chiavetta USB)

cd /d "%~dp0"

REM Cerca Python
where python >nul 2>&1
if %errorlevel%==0 (
    set PYTHON=python
) else (
    where python3 >nul 2>&1
    if %errorlevel%==0 (
        set PYTHON=python3
    ) else (
        echo ERRORE: Python non trovato!
        echo Scarica Python da https://www.python.org/downloads/
        echo Assicurati di selezionare "Add to PATH" durante l'installazione.
        pause
        exit /b 1
    )
)

REM Verifica tkinter
%PYTHON% -c "import tkinter" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERRORE: tkinter non disponibile.
    echo Reinstalla Python selezionando "tcl/tk and IDLE" nelle opzioni.
    pause
    exit /b 1
)

REM Installa Pillow se manca
%PYTHON% -c "from PIL import Image" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installazione Pillow...
    %PYTHON% -m pip install --user Pillow
)

REM Avvia
%PYTHON% "%~dp0main.py"
