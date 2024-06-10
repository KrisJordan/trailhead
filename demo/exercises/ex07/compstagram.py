"""Compstagram Demo"""

__template__ = "https://24s.comp110.com/static/compstagram/"


from .support import (
    Bitmap,
    Color,
    Request,
    Base64ImageStr,
    bitmap_to_base64,
    FilterSettings,
)


def main(request: Request) -> Base64ImageStr:
    """Primary entrypoint to the Compstagram backend."""
    image: Bitmap = request.image
    for filter in request.filters:
        image = filter.process(image)
    return bitmap_to_base64(image)


def get_filter_types() -> list[FilterSettings]:
    """Produces a list of default FilterSettings users can choose from."""
    return [
        FilterSettings(name="InvertFilter", amount=1.0),
        FilterSettings(name="BorderFilter", amount=0.1),
    ]


class InvertFilter:
    amount: float

    def __init__(self, amount: float):
        self.amount = amount

    def process(self, bitmap: Bitmap) -> Bitmap:
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
    amount: float
    color: Color

    def __init__(self, amount: float):
        self.amount = amount
        self.color = Color(75, 156, 211)

    def process(self, bitmap: Bitmap) -> Bitmap:
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
