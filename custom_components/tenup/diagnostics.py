"""Diagnostics for Ten'Up (cookie redacted)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_COOKIE

TO_REDACT = {CONF_COOKIE}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "fetched_at": data.fetched_at.isoformat() if data.fetched_at else None,
        "courts": [{"id": c.id, "name": c.name} for c in data.courts],
        "days": {
            day.isoformat(): {
                "free": len(p.free_slots),
                "mine": len(p.my_slots),
                "total": len(p.slots),
                "logged_in": p.logged_in,
            }
            for day, p in sorted(data.plannings.items())
        },
    }
