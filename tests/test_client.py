"""Tests for the BIR API client."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import (
    ClientConnectionError,
    ClientResponseError,
    ClientSession,
    RequestInfo,
)
from yarl import URL

from pybirno import (
    Address,
    BirAuthenticationError,
    BirClient,
    BirConnectionError,
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
        assert pickups[0].waste_type == "food_waste"
        assert pickups[0].waste_type_name == "Matavfall"
        assert pickups[0].waste_type_id == "3"
        assert pickups[1].date == date(2026, 4, 15)
        assert pickups[1].waste_type == "mixed_waste"
        assert pickups[1].waste_type_name == "Restavfall"

    async def test_get_pickups_auth_error(self, session: AsyncMock) -> None:
        """Test get_pickups raises immediately when initial auth fails."""
        session.post.return_value = _make_response(status=401)

        client = BirClient("prop-id", session)
        with pytest.raises(BirAuthenticationError):
            await client.get_pickups()

        # Should only attempt auth once, no retry
        assert session.post.call_count == 1
        # Should never reach the API call
        session.get.assert_not_called()

    async def test_get_pickups_reauth_on_expired_token(
        self,
        session: AsyncMock,
    ) -> None:
        """Test get_pickups re-authenticates on expired token and retries."""
        session.post.return_value = _make_response(headers={"Token": "new-token"})
        # First call returns 500 (BIR's response for expired token),
        # second call succeeds after re-auth
        session.get.side_effect = [
            _make_response(status=500),
            _make_response(
                json_data=[
                    {
                        "dato": "2026-04-15T00:00:00",
                        "fraksjon": "Restavfall",
                        "fraksjonId": "1",
                        "frekvensType": 2,
                        "frekvensIntervall": 2,
                    },
                ]
            ),
        ]

        client = BirClient("prop-id", session)
        pickups = await client.get_pickups()

        assert len(pickups) == 1
        assert pickups[0].waste_type == "mixed_waste"
        # Initial auth + re-auth
        assert session.post.call_count == 2

    async def test_get_pickups_reauth_fails(self, session: AsyncMock) -> None:
        """Test get_pickups raises when re-auth after token expiry also fails."""
        # First auth succeeds, re-auth fails
        session.post.side_effect = [
            _make_response(headers={"Token": "old-token"}),
            _make_response(status=401),
        ]
        # API returns 500 (expired token)
        session.get.return_value = _make_response(status=500)

        client = BirClient("prop-id", session)
        with pytest.raises(BirAuthenticationError):
            await client.get_pickups()

        assert session.post.call_count == 2

    async def test_get_pickups_server_error_retries_once(
        self, session: AsyncMock
    ) -> None:
        """Test 500 triggers one re-auth attempt.

        BIR uses 500 for expired tokens.
        """
        session.post.return_value = _make_response(headers={"Token": "test-token"})
        # Both attempts return 500
        session.get.return_value = _make_response(status=500)

        client = BirClient("prop-id", session)
        with pytest.raises(BirAuthenticationError):
            await client.get_pickups()

        # Initial auth + one re-auth attempt
        assert session.post.call_count == 2

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
        assert pickups[0].waste_type == "paper_and_plastic"
        assert pickups[0].waste_type_name == "Papir"

    async def test_get_pickups_connection_error(self, session: AsyncMock) -> None:
        """Test get_pickups raises BirConnectionError on connection failure."""
        session.post.return_value = _make_response(headers={"Token": "test-token"})
        session.get.side_effect = ClientConnectionError("Connection refused")

        client = BirClient("prop-id", session)
        with pytest.raises(BirConnectionError, match="Connection refused"):
            await client.get_pickups()

    async def test_get_pickups_timeout(self, session: AsyncMock) -> None:
        """Test get_pickups raises BirConnectionError on timeout."""
        session.post.return_value = _make_response(headers={"Token": "test-token"})
        session.get.side_effect = TimeoutError("Request timed out")

        client = BirClient("prop-id", session)
        with pytest.raises(BirConnectionError, match="Timeout"):
            await client.get_pickups()

    async def test_authenticate_timeout(self, session: AsyncMock) -> None:
        """Test authenticate raises BirConnectionError on timeout."""
        session.post.side_effect = TimeoutError("Request timed out")

        client = BirClient("prop-id", session)
        with pytest.raises(BirConnectionError, match="Timeout"):
            await client.authenticate()

    async def test_get_pickups_invalid_json(self, session: AsyncMock) -> None:
        """Test get_pickups raises BirConnectionError on invalid JSON."""
        session.post.return_value = _make_response(headers={"Token": "test-token"})
        mock_resp = _make_response()
        mock_resp.__aenter__.return_value.status = 200
        mock_resp.__aenter__.return_value.json = AsyncMock(
            side_effect=ValueError("Invalid JSON")
        )
        session.get.return_value = mock_resp

        client = BirClient("prop-id", session)
        with pytest.raises(BirConnectionError, match="Invalid response"):
            await client.get_pickups()


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

    async def test_search_skips_non_dict_items(self, session: AsyncMock) -> None:
        """Test that non-dict items in search results are skipped."""
        session.get.return_value = _make_response(
            json_data=[
                "unexpected string",
                {"Id": "abc-123", "Title": "Valid", "SubTitle": "Bergen"},
                None,
            ]
        )

        results = await BirClient.search_addresses(session, "Test")

        assert len(results) == 1
        assert results[0].property_id == "abc-123"

    async def test_search_connection_error(self, session: AsyncMock) -> None:
        """Test search raises BirConnectionError on failure."""
        session.get.return_value = _make_response(status=500)

        with pytest.raises(BirConnectionError):
            await BirClient.search_addresses(session, "Test")

    async def test_search_timeout(self, session: AsyncMock) -> None:
        """Test search raises BirConnectionError on timeout."""
        session.get.side_effect = TimeoutError("Request timed out")

        with pytest.raises(BirConnectionError, match="Timeout"):
            await BirClient.search_addresses(session, "Test")


class TestValidate:
    """Tests for BirClient.validate."""

    async def test_validate_success(self, session: AsyncMock) -> None:
        """Test validate returns True on success."""
        session.post.return_value = _make_response(headers={"Token": "valid-token"})
        session.get.return_value = _make_response(json_data=[])

        client = BirClient("prop-id", session)
        result = await client.validate()

        assert result is True
        session.post.assert_called_once()
        session.get.assert_called_once()


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
                "fraksjon": "Restavfall",
                "fraksjonId": "1",
                "frekvensType": 2,
                "frekvensIntervall": 2,
            },
            {
                "dato": "2026-04-05T00:00:00",
                "fraksjon": "Matavfall",
                "fraksjonId": "3",
                "frekvensType": 2,
                "frekvensIntervall": 1,
            },
        ]
        result = BirClient._parse_pickups(data)
        assert result[0].waste_type == "food_waste"
        assert result[1].waste_type == "mixed_waste"

    def test_missing_fraksjon_skipped(self) -> None:
        """Test that entries without fraksjon are skipped."""
        data = [{"dato": "2026-04-15T00:00:00"}]
        result = BirClient._parse_pickups(data)
        assert result == []

    def test_unknown_waste_type_skipped(self) -> None:
        """Test that unknown waste types are silently skipped."""
        data = [
            {
                "dato": "2026-04-10T00:00:00",
                "fraksjon": "Matavfall",
                "fraksjonId": "3",
                "frekvensType": 0,
                "frekvensIntervall": 0,
            },
            {
                "dato": "2026-04-15T00:00:00",
                "fraksjon": "Ukjent Type",
                "fraksjonId": "99",
                "frekvensType": 0,
                "frekvensIntervall": 0,
            },
        ]
        result = BirClient._parse_pickups(data)
        assert len(result) == 1
        assert result[0].waste_type == "food_waste"

    def test_frozen_dataclass(self) -> None:
        """Test that WastePickup is immutable."""
        pickup = WastePickup(
            date=date(2026, 4, 15),
            waste_type="mixed_waste",
            waste_type_name="Restavfall",
            waste_type_id="1",
            frequency_type=2,
            frequency_interval=2,
        )
        with pytest.raises(AttributeError):
            pickup.date = date(2026, 5, 1)  # type: ignore[misc]

    def test_non_dict_items_skipped(self) -> None:
        """Test that non-dict items in pickup data are skipped."""
        data = [
            "unexpected string",
            42,
            {
                "dato": "2026-04-15T00:00:00",
                "fraksjon": "Restavfall",
                "fraksjonId": "1",
                "frekvensType": 2,
                "frekvensIntervall": 2,
            },
            None,
        ]
        result = BirClient._parse_pickups(data)
        assert len(result) == 1
        assert result[0].waste_type == "mixed_waste"
