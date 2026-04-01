"""Integration tests that call the real BIR API.

These tests are skipped by default and only run in the scheduled CI workflow.
They verify that the library works correctly against the live API.

Run manually with: pytest tests/test_integration.py -m integration
"""

from __future__ import annotations

import pytest
from aiohttp import ClientSession

from pybirno import BirClient
from pybirno.const import API_LOGIN_URL, API_PICKUPS_URL

pytestmark = pytest.mark.integration


class TestLiveAuthentication:
    """Test authentication against the real BIR API."""

    async def test_authenticate_succeeds(self) -> None:
        """Test that authentication with public credentials succeeds."""
        async with ClientSession() as session:
            client = BirClient("dummy-property-id", session)
            await client.authenticate()

            assert client._token is not None
            assert len(client._token) > 0

    async def test_authenticate_bad_credentials_returns_400(self) -> None:
        """Test that invalid credentials return 400.

        The BIR API returns 400 (not 401) for bad credentials.
        """
        async with (
            ClientSession() as session,
            session.post(
                API_LOGIN_URL,
                json={
                    "applikasjonsId": "bad-app-id",
                    "oppdragsgiverId": "100",
                },
            ) as response,
        ):
            assert response.status == 400


class TestLiveTokenExpiry:
    """Test token expiry handling against the real BIR API."""

    async def test_invalid_token_returns_500(self) -> None:
        """Test that an invalid token gets 500 from the API.

        The BIR API returns 500 (not 401/403) for invalid tokens.
        This is why our client treats 500 on pickups as a token issue.
        """
        async with (
            ClientSession() as session,
            session.get(
                API_PICKUPS_URL,
                headers={"Token": "invalid-token"},
                params={
                    "eiendomId": "00000000-0000-0000-0000-000000000000",
                    "datoFra": "2026-04-01",
                    "datoTil": "2026-06-01",
                },
            ) as response,
        ):
            assert response.status == 500

    async def test_missing_token_returns_500(self) -> None:
        """Test that a missing token gets 500 from the API."""
        async with (
            ClientSession() as session,
            session.get(
                API_PICKUPS_URL,
                params={
                    "eiendomId": "00000000-0000-0000-0000-000000000000",
                    "datoFra": "2026-04-01",
                    "datoTil": "2026-06-01",
                },
            ) as response,
        ):
            assert response.status == 500

    async def test_get_pickups_with_invalid_token_triggers_reauth(self) -> None:
        """Test that get_pickups re-authenticates when token is stale.

        Sets a fake token, calls get_pickups, and verifies that the client
        transparently re-authenticates and returns data (empty list for a
        non-existent property is fine).
        """
        async with ClientSession() as session:
            client = BirClient("00000000-0000-0000-0000-000000000000", session)
            # Set a stale token to force re-auth on first API call
            client._token = "stale-invalid-token"

            # Should re-authenticate and succeed (empty list for fake property)
            pickups = await client.get_pickups()
            assert isinstance(pickups, list)


class TestLiveAddressSearch:
    """Test address search against the real BIR API."""

    async def test_search_returns_results(self) -> None:
        """Test that searching for a known street returns results."""
        async with ClientSession() as session:
            results = await BirClient.search_addresses(session, "Olav Kyrres")

            assert len(results) > 0
            assert results[0].property_id
            assert results[0].address

    async def test_search_no_results(self) -> None:
        """Test that searching for nonsense returns empty list."""
        async with ClientSession() as session:
            results = await BirClient.search_addresses(session, "xyznonexistent12345")

            assert results == []
