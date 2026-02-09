"""Utility per gestire immagini: PIL -> QPixmap."""

from __future__ import annotations

import io
import os

from PIL import Image
from PySide6.QtGui import QImage, QPixmap


def pil_to_pixmap(pil_image: Image.Image) -> QPixmap:
    """Convert a PIL Image to QPixmap."""
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    buf.seek(0)
    qimg = QImage()
    qimg.loadFromData(buf.getvalue())
    return QPixmap.fromImage(qimg)


def load_image_as_pixmap(path: str, max_width: int | None = None, max_height: int | None = None) -> QPixmap:
    """Load an image file and return a QPixmap, optionally resized."""
    img: Image.Image = Image.open(path)
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    if max_width or max_height:
        img = resize_contain(img, max_width or img.width, max_height or img.height)

    return pil_to_pixmap(img)


def resize_contain(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    """Resize image to fit within max_w x max_h maintaining aspect ratio."""
    w, h = img.size
    if w <= max_w and h <= max_h:
        return img
    ratio = min(max_w / w, max_h / h)
    new_size = (int(w * ratio), int(h * ratio))
    return img.resize(new_size, Image.Resampling.LANCZOS)


def is_image_file(path: str) -> bool:
    """Check if a file path looks like an image."""
    ext = os.path.splitext(path)[1].lower()
    return ext in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}
