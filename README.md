# pybirno

[![CI](https://github.com/SanderBlom/pybirno/actions/workflows/ci.yml/badge.svg)](https://github.com/SanderBlom/pybirno/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pybirno)](https://pypi.org/project/pybirno/)
[![Python](https://img.shields.io/pypi/pyversions/pybirno)](https://pypi.org/project/pybirno/)
[![License](https://img.shields.io/github/license/SanderBlom/pybirno)](https://github.com/SanderBlom/pybirno/blob/main/LICENSE)

Async Python client for the [BIR](https://bir.no) waste collection API. BIR handles garbage collection in the Bergen region of Norway. This library wraps a small part of their API (address lookup, auth, and pickup schedules) and was made to power the Home Assistant BIR integration.

## Installation

```bash
pip install pybirno
```

## Usage

### Fetching pickups

```python
import asyncio
from aiohttp import ClientSession
from pybirno import BirClient

async def main():
    async with ClientSession() as session:
        client = BirClient("property-id", session)
        pickups = await client.get_pickups()
        for pickup in pickups:
            print(f"{pickup.waste_type}: {pickup.date}")

asyncio.run(main())
```

### Searching for addresses

Find your property ID by searching for an address:

```python
async def find_address():
    async with ClientSession() as session:
        addresses = await BirClient.search_addresses(session, "Testveien 1")
        for addr in addresses:
            print(f"{addr.address} (ID: {addr.property_id})")
```

### Error handling

```python
from pybirno import BirClient, BirAuthenticationError, BirConnectionError

async def safe_fetch():
    async with ClientSession() as session:
        client = BirClient("property-id", session)
        try:
            pickups = await client.get_pickups()
        except BirAuthenticationError:
            print("Authentication failed")
        except BirConnectionError:
            print("Could not reach BIR API")
```

## API Documentation

- API spec: https://webservice.bir.no/swagger/docs/v1

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## Security

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.
