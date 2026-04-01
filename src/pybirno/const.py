"""Constants for the pybirno library."""

from typing import Final

API_BASE_URL: Final = "https://webservice.bir.no/api"
API_LOGIN_URL: Final = f"{API_BASE_URL}/login"
API_PROPERTIES_URL: Final = f"{API_BASE_URL}/v1/renovasjon/eiendommer"
API_PICKUPS_URL: Final = f"{API_BASE_URL}/v1/renovasjon/tomminger"

# Address search uses the BIR website API which has a broader address database.
API_ADDRESS_SEARCH_URL: Final = "https://bir.no/api/search/AddressSearch"

# Public application credentials used by the BIR website.
API_APP_ID: Final = "94FA72AD-583D-4AA3-988F-491F694DFB7B"
API_PROVIDER_ID: Final = "100;300;400"

API_TIMEOUT: Final = 30

# HTTP status code that BIR returns for expired/invalid tokens.
HTTP_SERVER_ERROR: Final = 500

# Mapping from Norwegian waste type names (from API) to English keys.
WASTE_TYPE_MAP: Final[dict[str, str]] = {
    "Restavfall": "mixed_waste",
    "Papir": "paper_and_plastic",
    "Matavfall": "food_waste",
    "Glass og metallemballasje": "glass_and_metal_packaging",
}
