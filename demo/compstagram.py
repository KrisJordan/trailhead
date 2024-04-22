"""Compstagram Demo"""

__template__ = "http://localhost:2100"

import base64
from io import BytesIO
from PIL import Image
from typing import Protocol
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


class Bitmap:
    pixels: list[list[Color]] = []


class Filter(Protocol):
    name: str
    amount: float

    def __init__(self, amount: float): ...
    def process(self, image: str) -> str: ...


FilterClass = type[Filter]


class InvertFilter:
    name: str = "Invert"
    amount: float

    def __init__(self, amount: float): ...

    def apply(self, bitmap: Bitmap) -> Bitmap:
        height: int = len(bitmap.pixels)
        width: int = len(bitmap.pixels[0])
        for y in range(height):
            for x in range(width):
                pixel = bitmap.pixels[y][x]
                pixel.red = 255 - pixel.red
                pixel.green = 255 - pixel.green
                pixel.blue = 255 - pixel.blue
        return bitmap


filter_types: dict[str, FilterClass] = {"Invert": InvertFilter}


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
    image = Image.new("RGB", (width, height))
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
    print(job_request.filters)
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
    return [FilterSettings(name="Invert", amount="1.0")]
