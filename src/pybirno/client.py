"""Async client for the BIR waste collection API."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout

from .const import (
    API_ADDRESS_SEARCH_URL,
    API_APP_ID,
    API_LOGIN_URL,
    API_PICKUPS_URL,
    API_PROVIDER_ID,
    API_TIMEOUT,
    WASTE_TYPE_MAP,
)
from .exceptions import (
    BirAuthenticationError,
    BirConnectionError,
    BirError,
)
from .models import Address, WastePickup

_LOGGER = logging.getLogger(__name__)


class BirClient:
    """Async client for the BIR waste collection API.

    Args:
        property_id: The property GUID from the BIR system.
        session: An aiohttp ClientSession to use for requests.

    """

    def __init__(self, property_id: str, session: ClientSession) -> None:
        """Initialize the BIR client."""
        self._property_id = property_id
        self._session = session
        self._token: str | None = None

    @property
    def property_id(self) -> str:
        """Return the property ID."""
        return self._property_id

    async def authenticate(self) -> None:
        """Authenticate with the BIR API and obtain a session token.

        Raises:
            BirAuthenticationError: If authentication fails.
            BirConnectionError: If a connection error occurs.

        """
        payload = {
            "applikasjonsId": API_APP_ID,
            "oppdragsgiverId": API_PROVIDER_ID,
        }

        timeout = ClientTimeout(total=API_TIMEOUT)
        try:
            async with self._session.post(
                API_LOGIN_URL, json=payload, timeout=timeout
            ) as response:
                response.raise_for_status()
                token = response.headers.get("Token")
                if not token:
                    raise BirAuthenticationError(
                        "Authentication failed: no token in response"
                    )
                self._token = token
                _LOGGER.debug("Authentication successful")
        except ClientResponseError as err:
            _LOGGER.debug("Authentication failed with status %s", err.status)
            raise BirAuthenticationError(
                f"Authentication failed: {err.status}"
            ) from err
        except ClientError as err:
            _LOGGER.debug("Connection error during authentication: %s", err)
            raise BirConnectionError(
                f"Connection error during authentication: {err}"
            ) from err
        except TimeoutError as err:
            _LOGGER.debug("Timeout during authentication")
            raise BirConnectionError("Timeout during authentication") from err

    async def get_pickups(self, days_ahead: int = 95) -> list[WastePickup]:
        """Fetch upcoming waste pickups for the property.

        Automatically re-authenticates once if the API rejects the token.

        Args:
            days_ahead: Number of days to look ahead. Defaults to 95.

        Returns:
            List of scheduled waste pickups, sorted by date.

        Raises:
            BirAuthenticationError: If authentication fails.
            BirConnectionError: If a connection error occurs.

        """
        await self._ensure_authenticated()
        try:
            return await self._fetch_pickups(days_ahead)
        except BirAuthenticationError:
            _LOGGER.debug("Token expired, re-authenticating")
            self._token = None
            await self.authenticate()
            return await self._fetch_pickups(days_ahead)

    async def _fetch_pickups(self, days_ahead: int) -> list[WastePickup]:
        """Fetch pickups from the API without retry logic.

        Args:
            days_ahead: Number of days to look ahead.

        Returns:
            List of scheduled waste pickups, sorted by date.

        Raises:
            BirAuthenticationError: If the token is invalid or expired.
            BirConnectionError: If a connection error occurs.

        """
        now = datetime.now(tz=UTC)
        params = {
            "eiendomId": self._property_id,
            "datoFra": now.strftime("%Y-%m-%d"),
            "datoTil": (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d"),
        }
        headers: dict[str, str] = {"Token": self._token or ""}

        timeout = ClientTimeout(total=API_TIMEOUT)
        try:
            async with self._session.get(
                API_PICKUPS_URL, headers=headers, params=params, timeout=timeout
            ) as response:
                if response.status in (401, 403):
                    raise BirAuthenticationError("Token expired or invalid")
                server_error_status = 500
                if response.status == server_error_status:
                    # The BIR API returns 500 for expired/invalid tokens
                    # rather than a proper 401/403.
                    raise BirAuthenticationError("Server error (likely expired token)")
                response.raise_for_status()
                data: list[dict[str, Any]] = await response.json()
        except BirError:
            raise
        except ClientResponseError as err:
            _LOGGER.debug("Error fetching pickups: %s", err)
            raise BirConnectionError(f"Error fetching pickups: {err}") from err
        except ClientError as err:
            _LOGGER.debug("Connection error fetching pickups: %s", err)
            raise BirConnectionError(
                f"Connection error fetching pickups: {err}"
            ) from err
        except TimeoutError as err:
            _LOGGER.debug("Timeout fetching pickups")
            raise BirConnectionError("Timeout fetching pickups") from err
        except ValueError as err:
            _LOGGER.debug("Invalid JSON in pickups response: %s", err)
            raise BirConnectionError(f"Invalid response from BIR API: {err}") from err

        return self._parse_pickups(data)

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid authentication token."""
        if self._token is None:
            _LOGGER.debug("No token present, authenticating")
            await self.authenticate()

    @staticmethod
    def _parse_pickups(data: list[dict[str, Any]]) -> list[WastePickup]:
        """Parse raw pickup data into WastePickup models.

        Args:
            data: Raw JSON data from the BIR API.

        Returns:
            List of WastePickup objects sorted by date.

        """
        pickups: list[WastePickup] = []
        for item in data:
            try:
                dato = item["dato"].split("T")[0]
                pickup_date = date.fromisoformat(dato)
                waste_type_name = item.get("fraksjon", "")
                waste_type = WASTE_TYPE_MAP.get(waste_type_name)
                if waste_type is None:
                    _LOGGER.debug("Skipping unknown waste type: %s", waste_type_name)
                    continue
                pickups.append(
                    WastePickup(
                        date=pickup_date,
                        waste_type=waste_type,
                        waste_type_name=waste_type_name,
                        waste_type_id=item.get("fraksjonId", ""),
                        frequency_type=item.get("frekvensType", 0),
                        frequency_interval=item.get("frekvensIntervall", 0),
                    )
                )
            except (KeyError, ValueError):
                _LOGGER.debug("Skipping malformed pickup entry: %s", item)
                continue

        _LOGGER.debug("Parsed %d pickups", len(pickups))
        return sorted(pickups, key=lambda p: p.date)

    @staticmethod
    async def search_addresses(session: ClientSession, query: str) -> list[Address]:
        """Search for addresses in the BIR service area.

        Uses the BIR website search API which covers all municipalities
        serviced by BIR (Bergen, Askøy, etc.).

        Args:
            session: An aiohttp ClientSession.
            query: Search string (street name, partial address, etc.).

        Returns:
            List of matching addresses.

        Raises:
            BirConnectionError: If a connection error occurs.

        """
        params = {"q": query, "s": "false"}
        timeout = ClientTimeout(total=API_TIMEOUT)

        try:
            async with session.get(
                API_ADDRESS_SEARCH_URL, params=params, timeout=timeout
            ) as response:
                response.raise_for_status()
                results: list[dict[str, Any]] = await response.json()
        except ClientError as err:
            _LOGGER.debug("Error searching addresses: %s", err)
            raise BirConnectionError(f"Error searching addresses: {err}") from err
        except TimeoutError as err:
            _LOGGER.debug("Timeout searching addresses")
            raise BirConnectionError("Timeout searching addresses") from err
        except ValueError as err:
            _LOGGER.debug("Invalid JSON in address search response: %s", err)
            raise BirConnectionError(f"Invalid response from BIR API: {err}") from err

        _LOGGER.debug(
            "Address search for '%s' returned %d results", query, len(results)
        )
        return [
            Address(
                property_id=item["Id"],
                address=f"{item.get('Title', '')}, {item.get('SubTitle', '')}",
                municipality=item.get("SubTitle", ""),
                municipality_number=item.get("MunicipalityNumber", ""),
            )
            for item in results
            if item.get("Id")
        ]

    async def validate(self) -> bool:
        """Validate that the client can authenticate and reach the API.

        Returns:
            True if the API is reachable and authentication succeeds.

        Raises:
            BirAuthenticationError: If authentication fails.
            BirConnectionError: If a connection error occurs.

        """
        await self.authenticate()
        return True
