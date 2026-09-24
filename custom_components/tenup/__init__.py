"""The Ten'Up integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .api import TenupAuthError, TenupClient, TenupConnectionError, new_session
from .const import CONF_CLUB_CODE, CONF_COOKIE, DOMAIN
from .coordinator import TenupCoordinator
from .http import async_setup_bookmarklet_page
from .services import async_setup_services
from .websocket import async_setup_websocket

PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type TenupConfigEntry = ConfigEntry[TenupCoordinator]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register services, websocket commands and the bookmarklet page once."""
    async_setup_services(hass)
    async_setup_websocket(hass)
    async_setup_bookmarklet_page(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TenupConfigEntry) -> bool:
    """Set up Ten'Up from a config entry."""
    session = new_session()
    client = TenupClient(
        session,
        entry.data[CONF_COOKIE],
        entry.data[CONF_CLUB_CODE],
        dt_util.get_default_time_zone(),
    )
    coordinator = TenupCoordinator(hass, entry, client)
    # Every way out of this block closes the session. A setup that fails is
    # retried every few minutes, and the first refresh raises ConfigEntryNotReady
    # or ConfigEntryAuthFailed far more often than it raises our own errors, so
    # closing only on those leaked one aiohttp session per attempt, for ever.
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except TenupAuthError as err:
        await session.close()
        raise ConfigEntryAuthFailed(str(err)) from err
    except TenupConnectionError as err:
        await session.close()
        raise ConfigEntryNotReady(str(err)) from err
    except BaseException:
        await session.close()
        raise

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: TenupConfigEntry) -> None:
    coordinator = getattr(entry, "runtime_data", None)
    # A cookie rotation saved by the coordinator also lands here, with the options
    # untouched: it must not reload the integration in the middle of a refresh.
    if coordinator is not None and coordinator.absorb_friends(entry):
        return  # only the friends list or the stored cookie changed: nothing to refetch
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TenupConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.session.close()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: TenupConfigEntry) -> None:
    """Forget the auth failure count of an entry that is being removed."""
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
