"""Constants for ro-etoll, maintained by Kosztyk."""

DOMAIN = "ro_etoll"
VERSION = "3.0.0-beta.4"
ATTRIBUTION = "Date furnizate de portal.etoll.ro"
BASE_URL = "https://portal.etoll.ro"
PORTAL_URL = f"{BASE_URL}/portal-extern/"
TOKEN_URL = "https://sso.etoll.ro/auth/realms/external/protocol/openid-connect/token"
CLIENT_ID = "ddcm-authz-client"
REQUEST_TIMEOUT = 30
# The portal uses 20; its VehicleService caps pages at 50. A size of 100 fails.
PAGE_SIZE = 20
MAX_PAGES = 100

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_ISTORIC_TRANZACTII = "istoric_tranzactii"
DEFAULT_UPDATE_INTERVAL = 3600
MIN_UPDATE_INTERVAL = 300
MAX_UPDATE_INTERVAL = 86400
ISTORIC_TRANZACTII_DEFAULT = 2
MAX_ATTR_TRECERI = 20
PLATFORMS = ["sensor"]
