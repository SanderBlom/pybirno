"""Tests for the BIR API client."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientResponseError, ClientSession, RequestInfo
from yarl import URL

from pybirno import (
    Address,
    BirAuthenticationError,
    BirClient,
    BirConnectionError,
    BirResponseError,
    WastePickup,
)


def _make_response(
    status: int = 200,
    headers: dict[str, str] | None = None,
    json_data: list | dict | None = None,
) -> AsyncMock:
    """Create a mock aiohttp response."""
    response = AsyncMock()
    response.status = status
    response.headers = headers or {}
    response.json = AsyncMock(return_value=json_data or [])

    if status >= 400:
        request_info = MagicMock(spec=RequestInfo)
        request_info.real_url = URL("https://example.com")
        response.raise_for_status = MagicMock(
            side_effect=ClientResponseError(
                request_info=request_info,
                history=(),
                status=status,
            )
        )
    else:
        response.raise_for_status = MagicMock()

    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    return response


@pytest.fixture
def session() -> AsyncMock:
    """Return a mock aiohttp session."""
    return AsyncMock(spec=ClientSession)


class TestAuthenticate:
    """Tests for BirClient.authenticate."""

    async def test_successful_auth(self, session: AsyncMock) -> None:
        """Test successful authentication returns token."""
        session.post.return_value = _make_response(headers={"Token": "test-token-123"})

        client = BirClient("prop-id", session)
        await client.authenticate()

        assert client._token == "test-token-123"
        session.post.assert_called_once()

    async def test_auth_no_token_in_response(self, session: AsyncMock) -> None:
        """Test authentication fails when no token in response."""
        session.post.return_value = _make_response(headers={})

        client = BirClient("prop-id", session)
        with pytest.raises(BirAuthenticationError, match="no token"):
            await client.authenticate()

    async def test_auth_http_error(self, session: AsyncMock) -> None:
        """Test authentication handles HTTP errors."""
        session.post.return_value = _make_response(status=401)

        client = BirClient("prop-id", session)
        with pytest.raises(BirAuthenticationError, match="401"):
            await client.authenticate()


class TestGetPickups:
    """Tests for BirClient.get_pickups."""

    async def test_get_pickups_success(self, session: AsyncMock) -> None:
        """Test fetching pickups returns parsed data."""
        # Mock login
        session.post.return_value = _make_response(headers={"Token": "test-token"})
        # Mock pickups
        session.get.return_value = _make_response(
            json_data=[
                {
                    "dato": "2026-04-15T00:00:00",
                    "fraksjon": "Restavfall",
                    "fraksjonId": "1",
                    "frekvensType": 2,
                    "frekvensIntervall": 2,
                },
                {
                    "dato": "2026-04-10T00:00:00",
                    "fraksjon": "Matavfall",
                    "fraksjonId": "3",
                    "frekvensType": 2,
                    "frekvensIntervall": 1,
                },
            ]
        )

        client = BirClient("prop-id", session)
        pickups = await client.get_pickups()

        assert len(pickups) == 2
        # Should be sorted by date
        assert pickups[0].date == date(2026, 4, 10)
        assert pickups[0].waste_type == "Matavfall"
        assert pickups[0].waste_type_id == "3"
        assert pickups[1].date == date(2026, 4, 15)
        assert pickups[1].waste_type == "Restavfall"

    async def test_get_pickups_auth_error(self, session: AsyncMock) -> None:
        """Test get_pickups raises on auth failure."""
        session.post.return_value = _make_response(headers={"Token": "test-token"})
        session.get.return_value = _make_response(status=401)

        client = BirClient("prop-id", session)
        with pytest.raises(BirAuthenticationError):
            await client.get_pickups()

    async def test_get_pickups_server_error(self, session: AsyncMock) -> None:
        """Test get_pickups raises BirResponseError on 500."""
        session.post.return_value = _make_response(headers={"Token": "test-token"})
        session.get.return_value = _make_response(status=500)

        client = BirClient("prop-id", session)
        with pytest.raises(BirResponseError):
            await client.get_pickups()

    async def test_get_pickups_auto_authenticates(self, session: AsyncMock) -> None:
        """Test get_pickups authenticates automatically if no token."""
        session.post.return_value = _make_response(headers={"Token": "auto-token"})
        session.get.return_value = _make_response(json_data=[])

        client = BirClient("prop-id", session)
        assert client._token is None

        pickups = await client.get_pickups()

        assert pickups == []
        assert client._token == "auto-token"
        session.post.assert_called_once()

    async def test_get_pickups_skips_malformed(self, session: AsyncMock) -> None:
        """Test that malformed entries are skipped."""
        session.post.return_value = _make_response(headers={"Token": "test-token"})
        session.get.return_value = _make_response(
            json_data=[
                {"dato": "invalid-date", "fraksjon": "Restavfall"},
                {
                    "dato": "2026-04-15T00:00:00",
                    "fraksjon": "Papir",
                    "fraksjonId": "2",
                    "frekvensType": 2,
                    "frekvensIntervall": 4,
                },
            ]
        )

        client = BirClient("prop-id", session)
        pickups = await client.get_pickups()

        assert len(pickups) == 1
        assert pickups[0].waste_type == "Papir"


class TestSearchAddresses:
    """Tests for BirClient.search_addresses."""

    async def test_search_success(self, session: AsyncMock) -> None:
        """Test successful address search."""
        session.get.return_value = _make_response(
            json_data=[
                {
                    "Id": "abc-123",
                    "Title": "Testveien 1",
                    "SubTitle": "Bergen",
                    "MunicipalityNumber": "4601",
                },
                {
                    "Id": "def-456",
                    "Title": "Testveien 2",
                    "SubTitle": "Askøy",
                    "MunicipalityNumber": "4627",
                },
            ]
        )

        results = await BirClient.search_addresses(session, "Testveien")

        assert len(results) == 2
        assert results[0] == Address(
            property_id="abc-123",
            address="Testveien 1, Bergen",
            municipality="Bergen",
            municipality_number="4601",
        )
        assert results[1].property_id == "def-456"

    async def test_search_skips_entries_without_id(self, session: AsyncMock) -> None:
        """Test that entries without an Id are filtered out."""
        session.get.return_value = _make_response(
            json_data=[
                {"Id": "abc-123", "Title": "Valid", "SubTitle": "Bergen"},
                {"Title": "No ID", "SubTitle": "Bergen"},
                {"Id": None, "Title": "Null ID", "SubTitle": "Bergen"},
            ]
        )

        results = await BirClient.search_addresses(session, "Test")

        assert len(results) == 1

    async def test_search_connection_error(self, session: AsyncMock) -> None:
        """Test search raises BirConnectionError on failure."""
        session.get.return_value = _make_response(status=500)

        with pytest.raises(BirConnectionError):
            await BirClient.search_addresses(session, "Test")


class TestValidate:
    """Tests for BirClient.validate."""

    async def test_validate_success(self, session: AsyncMock) -> None:
        """Test validate returns True on success."""
        session.post.return_value = _make_response(headers={"Token": "valid-token"})

        client = BirClient("prop-id", session)
        result = await client.validate()

        assert result is True


class TestParsePickups:
    """Tests for BirClient._parse_pickups static method."""

    def test_empty_data(self) -> None:
        """Test parsing empty list."""
        assert BirClient._parse_pickups([]) == []

    def test_sorted_output(self) -> None:
        """Test pickups are sorted by date."""
        data = [
            {
                "dato": "2026-04-20T00:00:00",
                "fraksjon": "B",
                "fraksjonId": "2",
                "frekvensType": 2,
                "frekvensIntervall": 2,
            },
            {
                "dato": "2026-04-05T00:00:00",
                "fraksjon": "A",
                "fraksjonId": "1",
                "frekvensType": 2,
                "frekvensIntervall": 1,
            },
        ]
        result = BirClient._parse_pickups(data)
        assert result[0].waste_type == "A"
        assert result[1].waste_type == "B"

    def test_missing_optional_fields(self) -> None:
        """Test parsing with missing optional fields uses defaults."""
        data = [{"dato": "2026-04-15T00:00:00"}]
        result = BirClient._parse_pickups(data)
        assert len(result) == 1
        assert result[0].waste_type == ""
        assert result[0].waste_type_id == ""
        assert result[0].frequency_type == 0
        assert result[0].frequency_interval == 0

    def test_frozen_dataclass(self) -> None:
        """Test that WastePickup is immutable."""
        pickup = WastePickup(
            date=date(2026, 4, 15),
            waste_type="Restavfall",
            waste_type_id="1",
            frequency_type=2,
            frequency_interval=2,
        )
        with pytest.raises(AttributeError):
            pickup.date = date(2026, 5, 1)  # type: ignore[misc]
