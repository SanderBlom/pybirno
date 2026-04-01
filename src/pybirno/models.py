"""Data models for the pybirno library."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date


@dataclass(frozen=True)
class WastePickup:
    """Represent a scheduled waste pickup."""

    date: date
    waste_type: str
    waste_type_id: str
    frequency_type: int
    frequency_interval: int


@dataclass(frozen=True)
class Address:
    """Represent a property address from the BIR API."""

    property_id: str
    address: str
    municipality: str
    municipality_number: str
