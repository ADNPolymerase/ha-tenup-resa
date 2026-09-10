"""Calendar of the account owner's reservations."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import TenupCoordinator
from .entity import TenupEntity
from .parser import Slot


def _event(slot: Slot, club_name: str) -> CalendarEvent:
    return CalendarEvent(
        start=slot.start,
        end=slot.end,
        summary=f"Tennis {slot.court_name}",
        description=f"{club_name} · réservation {slot.reservation_id or ''}".strip(),
        uid=f"tenup-{slot.reservation_id or slot.slot_id}-{slot.start:%Y%m%d}",
    )


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([TenupCalendar(entry.runtime_data)])


class TenupCalendar(TenupEntity, CalendarEntity):
    _attr_translation_key = "reservations"

    def __init__(self, coordinator: TenupCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.club_code}_reservations"

    @property
    def _club_name(self) -> str:
        return self.coordinator.entry.data.get("club_name") or self.club_code

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        for slot in self.coordinator.data.my_slots:
            if slot.end > now:
                return _event(slot, self._club_name)
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [
            _event(slot, self._club_name)
            for slot in self.coordinator.data.my_slots
            if slot.end > start_date and slot.start < end_date
        ]
