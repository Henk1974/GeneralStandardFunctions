"""Barcodes (EAN-8, EAN-13, UPC) normaliseren.

Laat elke ingang (scanner, handmatige invoer, externe API, import) door
``normalize_barcode`` gaan, zodat dezelfde barcode nooit als twee
verschillende waarden wordt opgeslagen.
"""

from __future__ import annotations

__all__ = ["InvalidBarcodeError", "normalize_barcode"]


class InvalidBarcodeError(ValueError):
    """De barcode is leeg of bevat iets anders dan cijfers."""


def normalize_barcode(barcode: str) -> str:
    """Normaliseer een barcode naar een vergelijkbare tekst.

    Witruimte rondom verdwijnt; leidende nullen blijven staan, want een
    barcode is een code en geen getal.

    Args:
        barcode: De gescande of getypte barcode.

    Returns:
        Alleen de cijfers, zonder witruimte rondom.

    Raises:
        InvalidBarcodeError: De barcode is leeg (of ``None``) of bevat
            andere tekens dan cijfers.

    Example:
        >>> normalize_barcode(" 0012345 ")
        '0012345'
    """
    stripped = (barcode or "").strip()
    if not stripped:
        raise InvalidBarcodeError("Barcode mag niet leeg zijn.")
    if not stripped.isdigit():
        raise InvalidBarcodeError(f"Barcode mag alleen cijfers bevatten, kreeg: {barcode!r}")
    return stripped
