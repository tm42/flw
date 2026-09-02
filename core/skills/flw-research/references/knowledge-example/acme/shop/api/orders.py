"""The order API. Toy: enough code for the store to mirror, and no more."""

from __future__ import annotations

ORDER_STATUS = ("placed", "shipped", "cancelled")


def place(item: str) -> dict:
    return {"item": item, "status": "placed"}
