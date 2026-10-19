"""Diagnostics for Ten'Up.

What comes out of here gets pasted into public issues, so two things never
leave the house: the session cookie, which signs its holder in, and the
friends list, which holds the names of other club members and, for a partner
remembered from the card, their Ten'Up member id.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_COOKIE, CONF_FRIENDS

TO_REDACT = {CONF_COOKIE, CONF_FRIENDS}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": async_redact_data(dict(entry.options), TO_REDACT),
        "fetched_at": data.fetched_at.isoformat() if data.fetched_at else None,
        "courts": [{"id": c.id, "name": c.name} for c in data.courts],
        "days": {
            day.isoformat(): {
                "free": len(p.free_slots),
                "mine": len(p.my_slots),
                "total": len(p.slots),
                "window_end": p.window_end.isoformat() if p.window_end else None,
            }
            for day, p in sorted(data.plannings.items())
        },
    }
