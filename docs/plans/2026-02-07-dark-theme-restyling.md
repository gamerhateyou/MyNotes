# Dark Theme Restyling — MyNotes

## Obiettivo

Restyling visivo completo dell'app con tema dark Obsidian-style. Solo colori, font e padding — nessun cambio di layout o widget. Palette centralizzata in `gui/constants.py` per manutenibilita futura.

## Palette colori

### Sfondo (3 livelli)

| Costante       | Valore    | Uso                                      |
|----------------|-----------|------------------------------------------|
| BG_DARK        | `#1e1e1e` | Sfondo principale (editor, finestra)     |
| BG_SURFACE     | `#252525` | Superfici elevate (sidebar, toolbar)     |
| BG_ELEVATED    | `#2d2d2d` | Elementi sopra superfici (listbox, entry)|

### Bordi

| Costante       | Valore    | Uso                          |
|----------------|-----------|------------------------------|
| BORDER         | `#3e3e3e` | Bordi standard               |
| BORDER_LIGHT   | `#4e4e4e` | Bordi hover / focus          |

### Testo (4 livelli)

| Costante       | Valore    | Uso                          |
|----------------|-----------|------------------------------|
| FG_PRIMARY     | `#dcddde` | Testo principale             |
| FG_SECONDARY   | `#888888` | Meta info, placeholder       |
| FG_MUTED       | `#666666` | Testo disabilitato           |
| FG_ON_ACCENT   | `#ffffff` | Testo su sfondo accento      |

### Accenti semantici

| Costante       | Valore    | Uso                          |
|----------------|-----------|------------------------------|
| ACCENT         | `#7aa2f7` | Selezione, link, focus       |
| ACCENT_HOVER   | `#89b4fa` | Hover su accento             |
| SUCCESS        | `#9ece6a` | Salvato, connesso            |
| WARNING        | `#e0af68` | Preferiti, pin               |
| DANGER         | `#f7768e` | Cestino, errori              |
| INFO           | `#7dcfff` | Audio markers                |

### Selezione

| Costante       | Valore    | Uso                          |
|----------------|-----------|------------------------------|
| SELECT_BG      | `#3d6fa5` | Sfondo selezione listbox     |
| SELECT_FG      | `#ffffff` | Testo selezione              |

### Font sizes (uniformati)

| Costante       | Valore | Uso                           |
|----------------|--------|-------------------------------|
| FONT_XS        | 8      | Gallery labels (era 7)        |
| FONT_SM        | 9      | Meta, sidebar header          |
| FONT_BASE      | 10     | Listbox, bottoni              |
| FONT_LG        | 11     | Editor                        |
| FONT_XL        | 14     | Titolo nota                   |

## File da modificare

### 1. `gui/constants.py`

Aggiungere tutte le costanti palette e font sizes. Zero rischi, nessun import cambia.

### 2. `gui/__init__.py`

Restyling setup TTK in `_setup_styles()`:

- `root.configure(bg=BG_DARK)`
- Aggiornare stili esistenti: `Toolbar.TFrame`, `Title.TLabel`, `Meta.TLabel`, `ImgPanel.TLabel`, `Pin.TLabel`
- Aggiungere stili base: `TFrame`, `TLabel`, `TEntry`, `TButton`, `TCombobox`, `TScrollbar`, `TPanedwindow`
- Combobox dropdown: `style.map("TCombobox", fieldbackground=[...])` per evitare dropdown bianco
- PanedWindow sash: `sashwidth=4` per divisore visibile
- Scrollbar: `troughcolor=BG_DARK`, `background=BORDER_LIGHT`

### 3. `gui/layout.py`

Solo parametri colore sui widget `tk.*`:

- Toolbar: `BG_SURFACE`
- Sidebar + cat_listbox: `BG_SURFACE`, `FG_PRIMARY`, `SELECT_BG`/`SELECT_FG`
- Sidebar label "CATEGORIE": `FG_SECONDARY`
- Note_listbox: `BG_ELEVATED`, `FG_PRIMARY`, `SELECT_BG`/`SELECT_FG`, `highlightcolor=BORDER`
- Text editor: `bg=BG_DARK`, `fg=FG_PRIMARY`, `insertbackground=FG_PRIMARY`, `selectbackground=ACCENT`, `selectforeground=FG_ON_ACCENT`
- Gallery canvas: `BG_ELEVATED`, `highlightbackground=BORDER`
- Gallery label font: `FONT_XS` (8pt)
- Gallery item bg: `BG_ELEVATED`, fg: `FG_SECONDARY`
- Status bar: sfondo coerente con tema
- Cestino: `DANGER`, Preferite: `WARNING`

### 4. `gui/note_window.py`

Stesse modifiche colore di layout.py per la finestra separata:

- Editor bg/fg/insertbackground
- Gallery canvas e labels
- Status bar
- Checklist tags e audio marker tags con palette

### 5. `gui/note_controller.py`

Colori inline:

- Drag floating label: `ACCENT` / `FG_ON_ACCENT`
- Category highlight drag: `SELECT_BG`
- Checklist tags: `FG_MUTED` (done), `FG_PRIMARY` (open)
- Audio marker tag: `INFO` su `BG_ELEVATED`
- Restore category color: `BG_SURFACE`

### 6. `dialogs.py`

Sfondo dark per tutti i dialog:

- `self.configure(bg=BG_SURFACE)` in ogni dialog `__init__`
- tk.Text e tk.Listbox nei dialog: `bg=BG_ELEVATED`, `fg=FG_PRIMARY`
- tk.Label/Frame nei dialog: `bg=BG_SURFACE`
- LabelFrame: `bg=BG_SURFACE`, `fg=FG_SECONDARY`
- Entry/Spinbox inline: colori dark

### 7. `annotator.py`

- Canvas bg: `BG_DARK`

### 8. `version.py`

- Bump versione

## Gotcha tkinter dark-theme

- **Cursore Text widget**: serve `insertbackground=FG_PRIMARY`, altrimenti cursore nero invisibile su sfondo dark
- **Combobox dropdown**: richiede `style.map()` separato per `fieldbackground` e `selectbackground`
- **Menu bar**: su Linux segue il tema GTK del sistema, non personalizzabile — lasciare com'e
- **Scrollbar clam**: personalizzabile con `troughcolor` e `background` sul thumb
- **PanedWindow sash**: quasi invisibile di default, servono `sashwidth=4` e colore esplicito
- **tk vs ttk**: widget `ttk.*` si colorano via Style, widget `tk.*` richiedono parametri inline
- **Dialog modali**: `tk.Toplevel` richiede `configure(bg=...)` esplicito; widget ttk dentro ereditano stili globali

## Ordine di implementazione

1. `constants.py` — palette (zero rischi)
2. `__init__.py` — stili TTK globali (colora tutti i ttk.* in un colpo)
3. `layout.py` — widget tk layout principale
4. `note_window.py` — finestra separata
5. `note_controller.py` — colori inline
6. `dialogs.py` — dialog modali
7. `annotator.py` — canvas bg
8. `version.py` — bump versione

Ogni passo testabile con `python3 main.py`.

## Verifica

1. `python3 -c "import py_compile; ..."` su tutti i file modificati
2. `python3 main.py` — verifica visiva:
   - Sfondo uniformemente dark
   - Testo leggibile (contrasto sufficiente)
   - Cursore editor visibile
   - Combobox dropdown dark
   - Scrollbar visibili
   - Sash PanedWindow visibile
   - Dialog tutti dark
   - Gallery labels leggibili (8pt)
   - Selezione listbox con colori corretti
   - Drag label coerente
   - Checklist e audio markers visibili
