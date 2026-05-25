from __future__ import annotations

from email.message import EmailMessage
from typing import Protocol, runtime_checkable

from ..models import Shipment


@runtime_checkable
class Parser(Protocol):
    name: str

    def matches(self, msg: EmailMessage) -> bool: ...

    def parse(self, msg: EmailMessage) -> Shipment: ...


REGISTRY: list[Parser] = []


def _load_all() -> None:
    from . import airmee, amazon, bring, zalando  # noqa: F401


_load_all()
