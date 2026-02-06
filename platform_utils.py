"""Utility cross-platform: apertura file, screenshot, font, rilevamento OS."""

import os
import sys
import platform
import subprocess

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MAC = sys.platform == "darwin"


def open_file(path):
    """Apri un file con l'applicazione predefinita del sistema."""
    if not os.path.exists(path):
        return False
    try:
        if IS_WINDOWS:
            os.startfile(path)
        elif IS_MAC:
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False


def get_font_path():
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


def get_ui_font():
    """Restituisce il nome del font UI migliore per la piattaforma."""
    if IS_WINDOWS:
        return "Segoe UI"
    elif IS_MAC:
        return "SF Pro"
    else:
        return "Sans"


def get_mono_font():
    """Restituisce il nome del font monospace migliore per la piattaforma."""
    if IS_WINDOWS:
        return "Consolas"
    elif IS_MAC:
        return "Menlo"
    else:
        return "Monospace"


def take_screenshot(save_path):
    """Cattura screenshot schermo intero, cross-platform."""
    if IS_WINDOWS or IS_MAC:
        return _screenshot_pil(save_path)
    else:
        return _screenshot_linux(save_path)


def take_screenshot_region(save_path):
    """Cattura screenshot di una regione, cross-platform."""
    if IS_WINDOWS or IS_MAC:
        # Su Windows/Mac catturiamo tutto, l'utente potrà ritagliare con l'annotatore
        return _screenshot_pil(save_path)
    else:
        return _screenshot_linux_region(save_path)


def _screenshot_pil(save_path):
    """Screenshot via PIL.ImageGrab (Windows/Mac/Linux con XCB)."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(save_path)
        return os.path.exists(save_path)
    except Exception:
        return False


def _screenshot_linux(save_path):
    """Screenshot su Linux con tool nativi."""
    import shutil

    # Wayland: grim
    if shutil.which("grim"):
        try:
            r = subprocess.run(["grim", save_path], capture_output=True, timeout=15)
            if r.returncode == 0 and os.path.exists(save_path):
                return True
        except Exception:
            pass

    # GNOME screenshot
    if shutil.which("gnome-screenshot"):
        try:
            r = subprocess.run(["gnome-screenshot", "-f", save_path], capture_output=True, timeout=15)
            if r.returncode == 0 and os.path.exists(save_path):
                return True
        except Exception:
            pass

    # X11: scrot
    if shutil.which("scrot"):
        try:
            r = subprocess.run(["scrot", save_path], capture_output=True, timeout=15)
            if r.returncode == 0 and os.path.exists(save_path):
                return True
        except Exception:
            pass

    # Fallback: PIL ImageGrab (funziona su X11 con python3-xlib)
    return _screenshot_pil(save_path)


def _screenshot_linux_region(save_path):
    """Screenshot regione su Linux."""
    import shutil

    # Wayland: grim + slurp
    if shutil.which("grim") and shutil.which("slurp"):
        try:
            slurp = subprocess.run(["slurp"], capture_output=True, text=True, timeout=60)
            if slurp.returncode == 0:
                region = slurp.stdout.strip()
                r = subprocess.run(["grim", "-g", region, save_path], capture_output=True, timeout=15)
                if r.returncode == 0 and os.path.exists(save_path):
                    return True
        except Exception:
            pass

    # GNOME screenshot area
    if shutil.which("gnome-screenshot"):
        try:
            r = subprocess.run(["gnome-screenshot", "-a", "-f", save_path], capture_output=True, timeout=60)
            if r.returncode == 0 and os.path.exists(save_path):
                return True
        except Exception:
            pass

    # scrot -s
    if shutil.which("scrot"):
        try:
            r = subprocess.run(["scrot", "-s", save_path], capture_output=True, timeout=60)
            if r.returncode == 0 and os.path.exists(save_path):
                return True
        except Exception:
            pass

    # Fallback: full screenshot
    return _screenshot_linux(save_path)
