"""Constants for ro_etoll, maintained by Kosztyk."""

DOMAIN = "ro_etoll"
VERSION = "1.0.0"
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
CONF_EXPIRY_WARNING_DAYS = "expiry_warning_days"
CONF_STALE_AFTER_HOURS = "stale_after_hours"
DEFAULT_EXPIRY_WARNING_DAYS = 15
DEFAULT_STALE_AFTER_HOURS = 2
DEFAULT_UPDATE_INTERVAL = 3600
MIN_UPDATE_INTERVAL = 300
MAX_UPDATE_INTERVAL = 86400
ISTORIC_TRANZACTII_DEFAULT = 2
MAX_ATTR_TRECERI = 20
PLATFORMS = ["sensor", "binary_sensor"]

DATA_SOURCES = {
    "vehicles": "vehicule",
    "vignettes": "roviniete",
    "bridges": "peaje",
    "invoices": "facturi",
    "notifications": "notificări",
    "services": "servicii cumpărate",
}
SERVICE_STATUSES = {
    "ACTIVE",
    "CANCELLED",
    "CONSUMED",
    "DRAFT",
    "EXPIRED",
    "REFUNDED",
    "PENDING",
}
PURCHASED_STATUSES = {"ACTIVE", "CONSUMED", "EXPIRED"}
