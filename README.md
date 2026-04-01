# pybirno

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
