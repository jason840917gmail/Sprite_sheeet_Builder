from __future__ import annotations

from PIL import Image
from PySide6.QtGui import QImage


def pil_to_qimage(image: Image.Image) -> QImage:
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    image_format = getattr(QImage, "Format_RGBA8888", QImage.Format.Format_RGBA8888)
    qimage = QImage(data, rgba.width, rgba.height, rgba.width * 4, image_format)
    return qimage.copy()

