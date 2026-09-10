"""Constants for the Ten'Up integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "tenup"

BASE_URL = "https://tenup.fft.fr"
PUBLIC_API = f"{BASE_URL}/back/public/v1"
QUEUE_ENQUEUE_URL = "https://tenup.queue-it.net/spa-api/queue/tenup/tenupprod/enqueue?cid=fr-FR"
QUEUE_HOST = "queue-it.net"

CONF_CLUB_CODE = "club_code"
CONF_CLUB_NAME = "club_name"
CONF_COOKIE = "cookie"
CONF_DAYS_AHEAD = "days_ahead"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_DAYS_AHEAD = 7
DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)
MIN_SCAN_INTERVAL_MINUTES = 5

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
