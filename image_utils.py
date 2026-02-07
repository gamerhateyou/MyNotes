"""Utility per gestire immagini: PIL -> QPixmap."""

from PySide6.QtGui import QPixmap, QImage
from PIL import Image
import io
import os


def pil_to_pixmap(pil_image):
    """Convert a PIL Image to QPixmap."""
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    buf.seek(0)
    qimg = QImage()
    qimg.loadFromData(buf.getvalue())
    return QPixmap.fromImage(qimg)


def load_image_as_pixmap(path, max_width=None, max_height=None):
    """Load an image file and return a QPixmap, optionally resized."""
    img = Image.open(path)
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    if max_width or max_height:
        img = resize_contain(img, max_width or img.width, max_height or img.height)

    return pil_to_pixmap(img)


def resize_contain(img, max_w, max_h):
    """Resize image to fit within max_w x max_h maintaining aspect ratio."""
    w, h = img.size
    if w <= max_w and h <= max_h:
        return img
    ratio = min(max_w / w, max_h / h)
    new_size = (int(w * ratio), int(h * ratio))
    return img.resize(new_size, Image.LANCZOS)


def is_image_file(path):
    """Check if a file path looks like an image."""
    ext = os.path.splitext(path)[1].lower()
    return ext in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}
