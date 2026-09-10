"""Data update coordinator for Ten'Up."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import TenupAuthError, TenupClient, TenupConnectionError
from .const import (
    CONF_DAYS_AHEAD,
    CONF_SCAN_INTERVAL,
    DEFAULT_DAYS_AHEAD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SLOT_FREE,
    SLOT_MINE,
)
from .parser import Planning, Slot

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class TenupData:
    """Everything the entities need."""

    plannings: dict[date, Planning] = field(default_factory=dict)
    fetched_at: datetime | None = None

    @property
    def courts(self) -> list:
        for planning in self.plannings.values():
            if planning.courts:
                return planning.courts
        return []

    @property
    def free_slots(self) -> list[Slot]:
        now = dt_util.now()
        return sorted(
            (s for p in self.plannings.values() for s in p.slots if s.state == SLOT_FREE and s.end > now),
            key=lambda s: (s.start, s.court_name),
        )

    @property
    def my_slots(self) -> list[Slot]:
        return sorted(
            (s for p in self.plannings.values() for s in p.slots if s.state == SLOT_MINE),
            key=lambda s: s.start,
        )

    def find_slot(self, court_id: str, start: datetime) -> Slot | None:
        planning = self.plannings.get(start.date())
        if planning is None:
            return None
        return planning.find(str(court_id), start)

    def find_reservation(self, reservation_id: str) -> Slot | None:
        for slot in self.my_slots:
            if slot.reservation_id == str(reservation_id):
                return slot
        return None


class TenupCoordinator(DataUpdateCoordinator[TenupData]):
    """Fetch the reservation grid for the coming days."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: TenupClient) -> None:
        minutes = entry.options.get(CONF_SCAN_INTERVAL)
        interval = timedelta(minutes=minutes) if minutes else DEFAULT_SCAN_INTERVAL
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data.get('club_code')}",
            update_interval=interval,
            config_entry=entry,
        )
        self.client = client
        self.entry = entry

    @property
    def days_ahead(self) -> int:
        return int(self.entry.options.get(CONF_DAYS_AHEAD, DEFAULT_DAYS_AHEAD))

    async def _async_update_data(self) -> TenupData:
        today = dt_util.now().date()
        data = TenupData()
        for offset in range(self.days_ahead):
            day = today + timedelta(days=offset)
            try:
                planning = await self.client.async_get_planning(day)
            except TenupAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except TenupConnectionError as err:
                if data.plannings:
                    _LOGGER.warning("Ten'Up: stopping at %s: %s", day, err)
                    break
                raise UpdateFailed(str(err)) from err
            data.plannings[day] = planning
            if planning.window_end and datetime.combine(
                day + timedelta(days=1), datetime.min.time(), planning.window_end.tzinfo
            ) > planning.window_end:
                break
        data.fetched_at = dt_util.now()
        return data

    async def async_book(self, slot: Slot) -> str:
        result = await self.client.async_book(slot)
        await self.async_request_refresh()
        return result

    async def async_cancel(self, slot: Slot) -> None:
        await self.client.async_cancel(slot)
        await self.async_request_refresh()
