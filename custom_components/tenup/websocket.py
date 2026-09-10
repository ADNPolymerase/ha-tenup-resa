"""Websocket command used by the companion card: the full planning."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


@callback
def async_setup_websocket(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_get_planning)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "tenup/planning",
        vol.Optional("entry_id"): str,
    }
)
@callback
def ws_get_planning(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return courts and every slot of every fetched day for one club."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if msg.get("entry_id"):
        entries = [e for e in entries if e.entry_id == msg["entry_id"]]
    entries = [e for e in entries if getattr(e, "runtime_data", None) is not None]
    if not entries:
        connection.send_error(msg["id"], "not_found", "No loaded Ten'Up entry")
        return
    coordinator = entries[0].runtime_data
    data = coordinator.data
    connection.send_result(
        msg["id"],
        {
            "entry_id": entries[0].entry_id,
            "club_code": entries[0].data.get("club_code"),
            "club_name": entries[0].data.get("club_name"),
            "fetched_at": data.fetched_at.isoformat() if data.fetched_at else None,
            "courts": [{"id": c.id, "name": c.name} for c in data.courts],
            "days": [
                {
                    "date": day.isoformat(),
                    "slots": [s.as_dict() for s in planning.slots],
                }
                for day, planning in sorted(data.plannings.items())
            ],
        },
    )
