"""Utility cross-platform: apertura file, screenshot, font, rilevamento OS."""

from __future__ import annotations

import os
import subprocess
import sys

IS_WINDOWS: bool = sys.platform == "win32"
IS_LINUX: bool = sys.platform.startswith("linux")
IS_MAC: bool = sys.platform == "darwin"

# Standard system paths to check when PATH is restricted (e.g. PyInstaller --windowed)
_SYSTEM_BIN_DIRS: tuple[str, ...] = ("/usr/bin", "/usr/local/bin", "/bin")


def _find_tool(name: str) -> str | None:
    """Find a system tool by name, checking PATH and common system locations."""
    import shutil

    path = shutil.which(name)
    if path:
        return path
    # Frozen builds may have restricted PATH; check standard locations
    for prefix in _SYSTEM_BIN_DIRS:
        candidate = os.path.join(prefix, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def open_file(path: str) -> bool:
    """Apri un file con l'applicazione predefinita del sistema."""
    if not os.path.exists(path):
        return False
    try:
        if IS_WINDOWS:
            os.startfile(path)  # type: ignore[attr-defined]
        elif IS_MAC:
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False


def get_font_path() -> str | None:
    """Trova un font TrueType disponibile nel sistema."""
    candidates = []
    if IS_WINDOWS:
        windir = os.environ.get("WINDIR", r"C:\Windows")
        candidates = [
            os.path.join(windir, "Fonts", "segoeui.ttf"),
            os.path.join(windir, "Fonts", "arial.ttf"),
            os.path.join(windir, "Fonts", "tahoma.ttf"),
        ]
    elif IS_MAC:
        candidates = [
            "/System/Library/Fonts/SFPro.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
    else:
        candidates = [
            # Fedora / GNOME
            "/usr/share/fonts/adwaita-sans-fonts/AdwaitaSans-Regular.ttf",
            "/usr/share/fonts/google-droid-sans-fonts/DroidSans.ttf",
            # DejaVu (varie distro)
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans.ttf",
            # Liberation (RHEL/Fedora)
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf",
            # Ubuntu / Debian
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
            # Noto
            "/usr/share/fonts/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/google-noto-vf/NotoSansMono[wght].ttf",
            # FreeFonts
            "/usr/share/fonts/gnu-free/FreeSans.ttf",
        ]
    for f in candidates:
        if os.path.exists(f):
            return f
    return None


def get_ui_font() -> str:
    """Restituisce il nome del font UI migliore per la piattaforma."""
    if IS_WINDOWS:
        return "Segoe UI"
    elif IS_MAC:
        return "SF Pro"
    else:
        return "Sans"


def get_mono_font() -> str:
    """Restituisce il nome del font monospace migliore per la piattaforma."""
    if IS_WINDOWS:
        return "Consolas"
    elif IS_MAC:
        return "Menlo"
    else:
        return "Monospace"


def take_screenshot(save_path: str) -> bool:
    """Cattura screenshot schermo intero, cross-platform."""
    if IS_WINDOWS or IS_MAC:
        return _screenshot_pil(save_path)
    else:
        return _screenshot_linux(save_path)


def take_screenshot_region(save_path: str) -> bool:
    """Cattura screenshot di una regione, cross-platform."""
    if IS_WINDOWS or IS_MAC:
        # Su Windows/Mac catturiamo tutto, l'utente potrà ritagliare con l'annotatore
        return _screenshot_pil(save_path)
    else:
        return _screenshot_linux_region(save_path)


def _screenshot_pil(save_path: str) -> bool:
    """Screenshot via PIL.ImageGrab (Windows/Mac/Linux con XCB)."""
    try:
        from PIL import ImageGrab

        img = ImageGrab.grab()
        img.save(save_path)
        return os.path.exists(save_path)
    except Exception:
        return False


def _screenshot_linux(save_path: str) -> bool:
    """Screenshot su Linux con tool nativi."""
    # Wayland: grim
    grim = _find_tool("grim")
    if grim:
        try:
            r = subprocess.run([grim, save_path], capture_output=True, timeout=15)
            if r.returncode == 0 and os.path.exists(save_path):
                return True
        except Exception:
            pass

    # GNOME screenshot
    gnome_ss = _find_tool("gnome-screenshot")
    if gnome_ss:
        try:
            r = subprocess.run([gnome_ss, "-f", save_path], capture_output=True, timeout=15)
            if r.returncode == 0 and os.path.exists(save_path):
                return True
        except Exception:
            pass

    # X11: scrot
    scrot = _find_tool("scrot")
    if scrot:
        try:
            r = subprocess.run([scrot, save_path], capture_output=True, timeout=15)
            if r.returncode == 0 and os.path.exists(save_path):
                return True
        except Exception:
            pass

    # Fallback: PIL ImageGrab (funziona su X11 con python3-xlib)
    return _screenshot_pil(save_path)


def _screenshot_linux_region(save_path: str) -> bool:
    """Screenshot regione su Linux."""
    # Wayland: grim + slurp
    grim = _find_tool("grim")
    slurp_bin = _find_tool("slurp")
    if grim and slurp_bin:
        try:
            slurp_proc = subprocess.run([slurp_bin], capture_output=True, text=True, timeout=60)
            if slurp_proc.returncode == 0:
                region = slurp_proc.stdout.strip()
                r = subprocess.run([grim, "-g", region, save_path], capture_output=True, timeout=15)
                if r.returncode == 0 and os.path.exists(save_path):
                    return True
        except Exception:
            pass

    # GNOME screenshot area
    gnome_ss = _find_tool("gnome-screenshot")
    if gnome_ss:
        try:
            r = subprocess.run([gnome_ss, "-a", "-f", save_path], capture_output=True, timeout=60)
            if r.returncode == 0 and os.path.exists(save_path):
                return True
        except Exception:
            pass

    # scrot -s
    scrot = _find_tool("scrot")
    if scrot:
        try:
            r = subprocess.run([scrot, "-s", save_path], capture_output=True, timeout=60)
            if r.returncode == 0 and os.path.exists(save_path):
                return True
        except Exception:
            pass

    # Fallback: full screenshot
    return _screenshot_linux(save_path)
