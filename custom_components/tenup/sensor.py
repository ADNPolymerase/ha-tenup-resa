"""Sensors for Ten'Up."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import TenupCoordinator, TenupData
from .entity import TenupEntity
from .parser import Slot

MAX_LISTED_SLOTS = 40


def _slot_attrs(slot: Slot) -> dict[str, Any]:
    return {
        "court_id": slot.court_id,
        "court_name": slot.court_name,
        "start": slot.start.isoformat(),
        "end": slot.end.isoformat(),
        "reservation_id": slot.reservation_id,
    }


def _free_today(data: TenupData) -> list[Slot]:
    today = dt_util.now().date()
    return [s for s in data.free_slots if s.start.date() == today]


@dataclass(frozen=True, kw_only=True)
class TenupSensorDescription(SensorEntityDescription):
    value_fn: Callable[[TenupData], Any]
    attrs_fn: Callable[[TenupData], dict[str, Any]] | None = None


DESCRIPTIONS: tuple[TenupSensorDescription, ...] = (
    TenupSensorDescription(
        key="free_slots_today",
        translation_key="free_slots_today",
        icon="mdi:tennis",
        value_fn=lambda d: len(_free_today(d)),
        attrs_fn=lambda d: {"slots": [_slot_attrs(s) for s in _free_today(d)[:MAX_LISTED_SLOTS]]},
    ),
    TenupSensorDescription(
        key="free_slots",
        translation_key="free_slots",
        icon="mdi:calendar-multiselect",
        value_fn=lambda d: len(d.free_slots),
        attrs_fn=lambda d: {
            "days": len(d.plannings),
            "per_day": {
                day.isoformat(): len([s for s in p.free_slots if s.end > dt_util.now()])
                for day, p in sorted(d.plannings.items())
            },
        },
    ),
    TenupSensorDescription(
        key="next_free_slot",
        translation_key="next_free_slot",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-start",
        value_fn=lambda d: d.free_slots[0].start if d.free_slots else None,
        attrs_fn=lambda d: _slot_attrs(d.free_slots[0]) if d.free_slots else {},
    ),
    TenupSensorDescription(
        key="next_reservation",
        translation_key="next_reservation",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-check",
        value_fn=lambda d: next((s.start for s in d.my_slots if s.end > dt_util.now()), None),
        attrs_fn=lambda d: next(
            (_slot_attrs(s) for s in d.my_slots if s.end > dt_util.now()), {}
        ),
    ),
    TenupSensorDescription(
        key="my_reservations",
        translation_key="my_reservations",
        icon="mdi:account-check",
        value_fn=lambda d: len([s for s in d.my_slots if s.end > dt_util.now()]),
        attrs_fn=lambda d: {
            "reservations": [_slot_attrs(s) for s in d.my_slots if s.end > dt_util.now()]
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: TenupCoordinator = entry.runtime_data
    async_add_entities(TenupSensor(coordinator, desc) for desc in DESCRIPTIONS)


class TenupSensor(TenupEntity, SensorEntity):
    entity_description: TenupSensorDescription

    def __init__(self, coordinator: TenupCoordinator, description: TenupSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self.club_code}_{description.key}"

    @property
    def native_value(self) -> Any:
        value = self.entity_description.value_fn(self.coordinator.data)
        if isinstance(value, datetime):
            return value
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        attrs = self.entity_description.attrs_fn(self.coordinator.data)
        if self.coordinator.data.fetched_at:
            attrs["fetched_at"] = self.coordinator.data.fetched_at.isoformat()
        return attrs
