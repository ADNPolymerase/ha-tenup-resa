"""Constants for the Ten'Up integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "tenup"

BASE_URL = "https://tenup.fft.fr"
# The member area runs on its own JSON API, authenticated by the session cookie
# alone. The public one, which needs no session, still answers the club search.
API = f"{BASE_URL}/api/back/v1"
PUBLIC_API = f"{BASE_URL}/back/public/v1"
QUEUE_ENQUEUE_URL = "https://tenup.queue-it.net/spa-api/queue/tenup/tenupprod/enqueue?cid=fr-FR"
QUEUE_HOST = "queue-it.net"

CONF_CLUB_CODE = "club_code"
CONF_CLUB_NAME = "club_name"
CONF_COOKIE = "cookie"
CONF_DAYS_AHEAD = "days_ahead"
CONF_FRIENDS = "friends"
CONF_SCAN_INTERVAL = "scan_interval"

# Key of the per-entry auth failure count kept in hass.data[DOMAIN][entry_id],
# so it outlives the coordinator that a failed setup throws away and rebuilds.
AUTH_FAILURES = "auth_failures"

DEFAULT_DAYS_AHEAD = 7
DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)
MIN_SCAN_INTERVAL_MINUTES = 5

# Best-effort per-refresh cap on eligibility calls used to learn how many
# players each distinct slot configuration (idCreneau) requires. Cached after.
MAX_PLAYER_LOOKUPS = 80

# The only offer that costs nothing: a subscription. A ticket book ("CA") debits
# a ticket and a single ticket is bought online, so neither is ever picked for
# the user. Ten'Up quotes the club's ticket rate on every offer, subscription
# included, so the price field cannot be used to tell them apart.
OFFER_SUBSCRIPTION = "AB"

SERVICE_BOOK = "book"
SERVICE_CANCEL = "cancel"

ATTR_COURT_ID = "court_id"
ATTR_START = "start"
ATTR_END = "end"
ATTR_RESERVATION_ID = "reservation_id"

# Slot states
SLOT_FREE = "free"
SLOT_BUSY = "busy"
SLOT_MINE = "mine"
SLOT_PAST = "past"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36 HomeAssistant-tenup"
)
