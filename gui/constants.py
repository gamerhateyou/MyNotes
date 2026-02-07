"""GUI constants shared across all controllers."""

import platform_utils

UI_FONT = platform_utils.get_ui_font()
MONO_FONT = platform_utils.get_mono_font()

AUTO_SAVE_MS = 800
VERSION_SAVE_EVERY = 5

# --- Dark Theme Palette (Obsidian-style) ---

# Backgrounds (3 depth levels)
BG_DARK = "#1e1e1e"          # Main background (editor, window)
BG_SURFACE = "#252525"       # Elevated surfaces (sidebar, toolbar)
BG_ELEVATED = "#2d2d2d"      # Elements on surfaces (listbox, entry)

# Borders
BORDER = "#3e3e3e"
BORDER_LIGHT = "#4e4e4e"

# Text hierarchy
FG_PRIMARY = "#dcddde"
FG_SECONDARY = "#888888"
FG_MUTED = "#666666"
FG_ON_ACCENT = "#ffffff"

# Semantic accents
ACCENT = "#7aa2f7"
ACCENT_HOVER = "#89b4fa"
SUCCESS = "#9ece6a"
WARNING = "#e0af68"
DANGER = "#f7768e"
INFO = "#7dcfff"

# Selection
SELECT_BG = "#3d6fa5"
SELECT_FG = "#ffffff"

# Font sizes
FONT_XS = 8
FONT_SM = 9
FONT_BASE = 10
FONT_LG = 11
FONT_XL = 14
