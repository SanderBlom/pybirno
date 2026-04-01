# pybirno

[![CI](https://github.com/SanderBlom/pybirno/actions/workflows/ci.yml/badge.svg)](https://github.com/SanderBlom/pybirno/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pybirno)](https://pypi.org/project/pybirno/)
[![Python](https://img.shields.io/pypi/pyversions/pybirno)](https://pypi.org/project/pybirno/)
[![License](https://img.shields.io/github/license/SanderBlom/pybirno)](https://github.com/SanderBlom/pybirno/blob/main/LICENSE)

Async Python client for the BIR waste collection API (Bergen, Norway).

## Installation

```bash
pip install pybirno
```

## Usage

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

## API Documentation

The BIR API Swagger docs are available at:
https://webservice.bir.no/swagger/docs/v1
