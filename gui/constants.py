"""GUI constants shared across all controllers."""

from __future__ import annotations

import platform_utils

UI_FONT: str = platform_utils.get_ui_font()
MONO_FONT: str = platform_utils.get_mono_font()

AUTO_SAVE_MS: int = 800
VERSION_SAVE_EVERY: int = 5

# --- Dark Theme Palette (Obsidian-style) ---

# Backgrounds (3 depth levels)
BG_DARK: str = "#1e1e1e"  # Main background (editor, window)
BG_SURFACE: str = "#252525"  # Elevated surfaces (sidebar, toolbar)
BG_ELEVATED: str = "#2d2d2d"  # Elements on surfaces (listbox, entry)

# Borders
BORDER: str = "#3e3e3e"
BORDER_LIGHT: str = "#4e4e4e"

# Text hierarchy
FG_PRIMARY: str = "#dcddde"
FG_SECONDARY: str = "#888888"
FG_MUTED: str = "#666666"
FG_ON_ACCENT: str = "#ffffff"

# Semantic accents
ACCENT: str = "#7aa2f7"
ACCENT_HOVER: str = "#89b4fa"
SUCCESS: str = "#9ece6a"
WARNING: str = "#e0af68"
DANGER: str = "#f7768e"
INFO: str = "#7dcfff"

# Selection
SELECT_BG: str = "#3d6fa5"
SELECT_FG: str = "#ffffff"

# Font sizes
FONT_XS: int = 8
FONT_SM: int = 9
FONT_BASE: int = 10
FONT_LG: int = 11
FONT_XL: int = 14
