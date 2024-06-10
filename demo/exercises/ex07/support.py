"""Transformations between representations of data."""

from io import BytesIO
from base64 import b64decode, b64encode
from PIL import Image
from pydantic import BaseModel
from typing import Self, Protocol


class Color:
    red: int
    green: int
    blue: int

    def __init__(self, red: int, green: int, blue: int):
        self.red = red
        self.green = green
        self.blue = blue

    def copy(self) -> Self:
        return Color(self.red, self.green, self.blue)


class Bitmap:
    pixels: list[list[Color]]
    width: int
    height: int

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.pixels = []
        for _y in range(height):
            row: list[Color] = []
            for _x in range(width):
                row.append(Color(0.0, 0.0, 0.0))
            self.pixels.append(row)

    def get_pixel(self, x: int, y: int) -> Color:
        return self.pixels[y][x]


class Filter(Protocol):
    def __init__(self, amount: float): ...
    def process(self, image: Bitmap) -> Bitmap: ...


# Type Alias
Base64ImageStr = str


class Request:
    image: Bitmap  # TODO Request
    filters: list[Filter]

    def __init__(self, image: str, filters: list[Filter]):
        self.image = bitmap_from_base64(image)
        self.filters = filters


class FilterSettings(BaseModel):
    name: str
    amount: float


def bitmap_from_base64(data: str) -> Bitmap:
    # Get Encoded String
    _, base64_encoded = data.split(",", 1)
    # Decode the String to Bytes
    buffer: BytesIO = BytesIO(b64decode(base64_encoded))
    # Load Bytes into Pillow Library (PIL) Image Class
    image: Image.Image = Image.open(buffer).convert("RGB")
    width, height = image.size
    # Copy Image Data into Bitmap Object
    bitmap: Bitmap = Bitmap(width, height)
    for y in range(height):
        for x in range(width):
            red, green, blue = image.getpixel((x, y))
            pixel: Color = bitmap.get_pixel(x, y)
            pixel.red = red
            pixel.green = green
            pixel.blue = blue
    return bitmap


def bitmap_to_base64(self: Bitmap) -> Base64ImageStr:
    # Initialize Pillow Image Class
    image: Image.Image = Image.new("RGB", (self.width, self.height))
    # Copy Pixel Data
    for y in range(self.height):
        for x in range(self.width):
            pixel: Color = self.get_pixel(x, y)
            image.putpixel((x, y), (pixel.red, pixel.green, pixel.blue))
    # Save Image data to Bytes buffer
    buffer: BytesIO = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    # Convert byte buffer to utf8 plaintext
    base64_encoded_utf8: str = b64encode(buffer.read()).decode("utf-8")
    # Return Data URL-encoded image string for the browser
    return "data:imgage/png;base64," + base64_encoded_utf8
