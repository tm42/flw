"""The fulfilment worker. Toy: enough code for the store to mirror, and no more."""

from __future__ import annotations


def drain(queue: list[dict]) -> list[dict]:
    return [{**order, "status": "shipped"} for order in queue]
