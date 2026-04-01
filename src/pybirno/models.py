"""Data models for the pybirno library."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date


@dataclass(frozen=True)
class WastePickup:
    """Represent a scheduled waste pickup.

    Attributes:
        date: The scheduled pickup date.
        waste_type: English key for the waste type (e.g. "mixed_waste").
        waste_type_name: Original Norwegian name from the API (e.g. "Restavfall").
        waste_type_id: Unique identifier for the waste type from the API.
        frequency_type: Pickup frequency type code from the API.
        frequency_interval: Number of intervals between pickups.

    """

    date: date
    waste_type: str
    waste_type_name: str
    waste_type_id: str
    frequency_type: int
    frequency_interval: int


@dataclass(frozen=True)
class Address:
    """Represent a property address from the BIR API.

    Attributes:
        property_id: The BIR property GUID used to fetch pickups.
        address: Formatted address string (e.g. "Testveien 1, Bergen").
        municipality: Municipality name (e.g. "Bergen").
        municipality_number: Official municipality number (e.g. "4601").

    """

    property_id: str
    address: str
    municipality: str
    municipality_number: str
