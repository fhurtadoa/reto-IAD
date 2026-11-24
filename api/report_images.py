"""Validated Plotly images shared by the Excel and PDF reports."""
from base64 import b64decode
from binascii import Error as Base64Error
from dataclasses import dataclass
from io import BytesIO
import re

from PIL import Image
from pydantic import BaseModel, Field


def report_text(text: str) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]", "", text)


class ChartInput(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    caption: str = Field(default="", max_length=50_000)
    png: str = Field(min_length=1, max_length=2_000_000)


@dataclass(frozen=True)
class ChartImage:
    title: str
    caption: str
    png: bytes
    width: int
    height: int

    @classmethod
    def from_input(cls, chart: ChartInput):
        try:
            png = b64decode(chart.png, validate=True)
            with Image.open(BytesIO(png), formats=["PNG"]) as image:
                width, height = image.size
                if not (0 < width <= 3000 and 0 < height <= 3000):
                    raise ValueError("Dimensiones fuera de rango")
                image.verify()
            # verify() checks the container. Decode pixels now so a corrupt
            # IDAT stream does not fail later in only one renderer.
            with Image.open(BytesIO(png), formats=["PNG"]) as image:
                image.load()
            return cls(report_text(chart.title).strip() or "Gráfica", report_text(chart.caption), png, width, height)
        except (ValueError, Base64Error, OSError, Image.DecompressionBombError) as error:
            raise ValueError(f"La gráfica «{report_text(chart.title)}» no contiene una imagen PNG válida.") from error
