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

# Some waste types (e.g. glass and metal packaging) are only collected
# every 3 months, so we need to look ahead at least 95 days to ensure
# all upcoming pickups are included.
DEFAULT_DAYS_AHEAD: Final = 95

# HTTP status codes for authentication-related errors.
HTTP_UNAUTHORIZED: Final = 401
HTTP_FORBIDDEN: Final = 403
HTTP_SERVER_ERROR: Final = 500

# Mapping from Norwegian waste type names (from API) to English keys.
WASTE_TYPE_MAP: Final[dict[str, str]] = {
    "Restavfall": "mixed_waste",
    "Papir": "paper_and_plastic",
    "Matavfall": "food_waste",
    "Glass og metallemballasje": "glass_and_metal_packaging",
}
