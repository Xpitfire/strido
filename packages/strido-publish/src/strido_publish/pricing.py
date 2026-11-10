"""Cost of buying a BOM line from one offer (packs rounded up) and money formatting."""

import math


def pieces_bought(line, offer) -> int:
    pack = offer.get("pack", 1)
    return math.ceil(line["qty"] / pack) * pack


def offer_cost(line, offer) -> float:
    return math.ceil(line["qty"] / offer.get("pack", 1)) * offer["price"]


def money(value: float) -> str:
    return f"€{value:,.2f}"
