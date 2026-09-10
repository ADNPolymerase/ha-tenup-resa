"""Services: book and cancel a court."""

from __future__ import annotations

from datetime import datetime

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .api import TenupAuthError, TenupBookingError, TenupConnectionError
from .const import (
    ATTR_COURT_ID,
    ATTR_RESERVATION_ID,
    ATTR_START,
    DOMAIN,
    SERVICE_BOOK,
    SERVICE_CANCEL,
)

ATTR_ENTRY_ID = "entry_id"

BOOK_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Required(ATTR_COURT_ID): cv.string,
        vol.Required(ATTR_START): cv.datetime,
    }
)
CANCEL_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Optional(ATTR_RESERVATION_ID): cv.string,
        vol.Optional(ATTR_COURT_ID): cv.string,
        vol.Optional(ATTR_START): cv.datetime,
    }
)


def _coordinators(hass: HomeAssistant, entry_id: str | None):
    entries = hass.config_entries.async_entries(DOMAIN)
    if entry_id:
        entries = [e for e in entries if e.entry_id == entry_id]
    loaded = [e for e in entries if hasattr(e, "runtime_data") and e.runtime_data is not None]
    if not loaded:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_entry"
        )
    return [e.runtime_data for e in loaded]


def _as_local(value: datetime) -> datetime:
    value = dt_util.as_local(value) if value.tzinfo else value.replace(tzinfo=dt_util.get_default_time_zone())
    return value.replace(second=0, microsecond=0)


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the services once per Home Assistant run."""
    if hass.services.has_service(DOMAIN, SERVICE_BOOK):
        return

    async def _book(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinators(hass, call.data.get(ATTR_ENTRY_ID))[0]
        start = _as_local(call.data[ATTR_START])
        slot = coordinator.data.find_slot(call.data[ATTR_COURT_ID], start)
        if slot is None:
            await coordinator.async_refresh()
            slot = coordinator.data.find_slot(call.data[ATTR_COURT_ID], start)
        if slot is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="slot_unknown",
                translation_placeholders={"court": call.data[ATTR_COURT_ID], "start": start.isoformat()},
            )
        if slot.state != "free":
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="slot_not_free",
                translation_placeholders={"court": slot.court_name, "start": start.isoformat(), "state": slot.state},
            )
        try:
            message = await coordinator.async_book(slot)
        except TenupBookingError as err:
            raise HomeAssistantError(f"Ten'Up: {err}") from err
        except TenupAuthError as err:
            coordinator.entry.async_start_reauth(hass)
            raise HomeAssistantError(f"Ten'Up: session expirée ({err})") from err
        except TenupConnectionError as err:
            raise HomeAssistantError(f"Ten'Up injoignable: {err}") from err
        return {"court_id": slot.court_id, "court_name": slot.court_name, "start": slot.start.isoformat(), "end": slot.end.isoformat(), "message": message}

    async def _cancel(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinators(hass, call.data.get(ATTR_ENTRY_ID))[0]
        slot = None
        if call.data.get(ATTR_RESERVATION_ID):
            slot = coordinator.data.find_reservation(call.data[ATTR_RESERVATION_ID])
        elif call.data.get(ATTR_COURT_ID) and call.data.get(ATTR_START):
            slot = coordinator.data.find_slot(call.data[ATTR_COURT_ID], _as_local(call.data[ATTR_START]))
        else:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="cancel_target_missing")
        if slot is None or slot.state != "mine":
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="reservation_unknown")
        try:
            await coordinator.async_cancel(slot)
        except TenupBookingError as err:
            raise HomeAssistantError(f"Ten'Up: {err}") from err
        except TenupAuthError as err:
            coordinator.entry.async_start_reauth(hass)
            raise HomeAssistantError(f"Ten'Up: session expirée ({err})") from err
        except TenupConnectionError as err:
            raise HomeAssistantError(f"Ten'Up injoignable: {err}") from err
        return {"court_id": slot.court_id, "court_name": slot.court_name, "start": slot.start.isoformat(), "reservation_id": slot.reservation_id, "cancelled": True}

    hass.services.async_register(DOMAIN, SERVICE_BOOK, _book, schema=BOOK_SCHEMA, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, SERVICE_CANCEL, _cancel, schema=CANCEL_SCHEMA, supports_response=SupportsResponse.OPTIONAL)
