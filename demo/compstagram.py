"""Compstagram Demo"""

__template__ = "http://localhost:2100"

import base64
from io import BytesIO
from PIL import Image
from typing import Protocol, Self
from pydantic import BaseModel


JobRequestJson = str
Base64PNGImage = str


class Color:
    red: int
    green: int
    blue: int

    def __init__(self, r: int, g: int, b: int):
        self.red = r
        self.green = g
        self.blue = b

    def copy(self) -> Self:
        return Color(self.red, self.green, self.blue)


class Bitmap:
    pixels: list[list[Color]]

    def __init__(self):
        self.pixels = []


class Filter(Protocol):
    name: str
    amount: float

    def __init__(self, amount: float): ...
    def process(self, image: str) -> str: ...


FilterClass = type[Filter]


class InvertFilter:
    name: str = "Invert"
    amount: float

    def __init__(self, amount: float):
        self.amount = amount

    def apply(self, bitmap: Bitmap) -> Bitmap:
        height: int = len(bitmap.pixels)
        width: int = len(bitmap.pixels[0])
        for y in range(height):
            for x in range(width):
                pixel = bitmap.pixels[y][x]
                red_inverted = 255 - pixel.red
                green_inverted = 255 - pixel.green
                blue_inverted = 255 - pixel.blue
                red_delta = int((red_inverted - pixel.red) * self.amount)
                green_delta = int((green_inverted - pixel.green) * self.amount)
                blue_delta = int((blue_inverted - pixel.blue) * self.amount)
                pixel.red += red_delta
                pixel.green += green_delta
                pixel.blue += blue_delta

        return bitmap


class BorderFilter:
    name: str = "Border"
    amount: float
    color: Color

    def __init__(self, amount: float):
        self.amount = amount
        self.color = Color(75, 156, 211)

    def apply(self, bitmap: Bitmap) -> Bitmap:
        height: int = len(bitmap.pixels)
        width: int = len(bitmap.pixels[0])
        thickness = int(width / 2 * self.amount)
        for x in range(thickness):
            for y in range(height):
                bitmap.pixels[y][x] = self.color.copy()
                bitmap.pixels[y][width - x - 1] = self.color.copy()

        for y in range(thickness):
            for x in range(width):
                bitmap.pixels[y][x] = self.color.copy()
                bitmap.pixels[height - y - 1][x] = self.color.copy()

        return bitmap


filter_types: dict[str, FilterClass] = {"Invert": InvertFilter, "Border": BorderFilter}


class FilterSettings(BaseModel):
    name: str
    amount: float


class JobRequest(BaseModel):
    image: Base64PNGImage
    filters: list[FilterSettings]


class Job:
    input: Bitmap
    filters: list[Filter]

    def run(self) -> Bitmap:
        result = self.input
        for filter in self.filters:
            result = filter.apply(result)
        return result


def loadImage(image_b64: str) -> Image.Image:
    _, encoded = image_b64.split(",", 1)
    binary_data = base64.b64decode(encoded)
    image_data = BytesIO(binary_data)
    return Image.open(image_data).convert("RGB")


def to_image(bitmap: Bitmap) -> str:
    # Convert to PIL Image
    height = len(bitmap.pixels)
    width = len(bitmap.pixels[0])
    image = Image.new("RGB", (width, height), "green")
    for y in range(height):
        for x in range(width):
            pixel = bitmap.pixels[y][x]
            image.putpixel((x, y), (pixel.red, pixel.green, pixel.blue))
    buffer: BytesIO = BytesIO()
    image.save(buffer, format="PNG")  # Using PNG to handle both RGB and RGBA
    buffer.seek(0)
    # Encode buffer to base64
    img_base64 = base64.b64encode(buffer.read())
    return "data:image/png;base64," + img_base64.decode("utf-8")


def main(job_json: JobRequestJson) -> Base64PNGImage:
    job_request = JobRequest.model_validate_json(job_json)
    job = Job()
    job.filters = []
    for filter_spec in job_request.filters:
        filter_class: FilterClass = filter_types[filter_spec.name]
        filter_instance: Filter = filter_class(filter_spec.amount)
        job.filters.append(filter_instance)

    image = loadImage(job_request.image)
    width, height = image.size
    job.input = Bitmap()
    for y in range(height):
        row = []
        for x in range(width):
            red, green, blue = image.getpixel((x, y))
            row.append(Color(red, green, blue))
        job.input.pixels.append(row)

    # Reverse-o
    return to_image(job.run())


def get_filter_types() -> list[FilterSettings]:
    """Produces a list of default FilterSettings users can choose from."""
    return [
        FilterSettings(name="Invert", amount="1.0"),
        FilterSettings(name="Border", amount="0.1"),
    ]
