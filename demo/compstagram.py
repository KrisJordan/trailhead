"""Compstagram Demo"""

import base64
from io import BytesIO
from PIL import Image, ImageFilter

__template__ = "http://localhost:2100"


def pixels_to_base64(img: Image.Image) -> str:
    # Save the image to a bytes buffer
    buffer: BytesIO = BytesIO()
    img.save(buffer, format="PNG")  # Using PNG to handle both RGB and RGBA
    buffer.seek(0)

    # Encode buffer to base64
    img_base64 = base64.b64encode(buffer.read())
    return "data:image/png;base64," + img_base64.decode("utf-8")


def loadImage(image_b64: str) -> str:
    _, encoded = image_b64.split(",", 1)
    binary_data = base64.b64decode(encoded)
    image_data = BytesIO(binary_data)
    img = Image.open(image_data)
    img = img.filter(ImageFilter.GaussianBlur(10))
    return pixels_to_base64(img)
