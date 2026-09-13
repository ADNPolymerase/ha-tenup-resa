"""Websocket command used by the companion card: the full planning."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .api import TenupError
from .const import CONF_FRIENDS, DOMAIN


@callback
def async_setup_websocket(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_get_planning)
    websocket_api.async_register_command(hass, ws_set_friends)
    websocket_api.async_register_command(hass, ws_search_partner)


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
            "friends": list(coordinator.friends),
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


@websocket_api.websocket_command(
    {
        vol.Required("type"): "tenup/partner/search",
        vol.Optional("entry_id"): str,
        vol.Required("query"): str,
    }
)
@websocket_api.async_response
async def ws_search_partner(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Search a club member to play with.

    The card shows the names and keeps the matching key out of sight, so nobody
    ever has to find a member id by hand: this is the same search the site's own
    partner field performs.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    if msg.get("entry_id"):
        entries = [e for e in entries if e.entry_id == msg["entry_id"]]
    entries = [e for e in entries if getattr(e, "runtime_data", None) is not None]
    if not entries:
        connection.send_error(msg["id"], "not_found", "No loaded Ten'Up entry")
        return
    try:
        results = await entries[0].runtime_data.client.async_search_partner(msg["query"])
    except TenupError as err:
        connection.send_error(msg["id"], "search_failed", str(err))
        return
    connection.send_result(
        msg["id"],
        {"results": [{"choice": choice, "name": name} for choice, name in results]},
    )


MAX_FRIENDS = 50
MIN_FRIEND_LENGTH = 3


def clean_friends(raw: list[str]) -> list[str]:
    """Trim, drop the unusable, and de-duplicate without regard to case.

    Very short entries are refused on purpose: Ten'Up labels club lessons with
    first names, so a two-letter entry would paint half the grid.
    """
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        name = " ".join(str(item).split())
        if len(name) < MIN_FRIEND_LENGTH:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out[:MAX_FRIENDS]


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "tenup/friends/set",
        vol.Optional("entry_id"): str,
        vol.Required("friends"): [str],
    }
)
@callback
def ws_set_friends(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Replace the friends list, stored in the config entry options."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if msg.get("entry_id"):
        entries = [e for e in entries if e.entry_id == msg["entry_id"]]
    entries = [e for e in entries if getattr(e, "runtime_data", None) is not None]
    if not entries:
        connection.send_error(msg["id"], "not_found", "No loaded Ten'Up entry")
        return
    entry = entries[0]
    friends = clean_friends(msg["friends"])
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_FRIENDS: friends}
    )
    connection.send_result(msg["id"], {"friends": friends})
