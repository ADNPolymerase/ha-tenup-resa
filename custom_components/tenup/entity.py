"""Base entity for Ten'Up."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CLUB_CODE, CONF_CLUB_NAME, DOMAIN
from .coordinator import TenupCoordinator


class TenupEntity(CoordinatorEntity[TenupCoordinator]):
    """Common device info: one device per club."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TenupCoordinator) -> None:
        super().__init__(coordinator)
        club_code = coordinator.entry.data[CONF_CLUB_CODE]
        club_name = coordinator.entry.data.get(CONF_CLUB_NAME) or f"Club {club_code}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, club_code)},
            name=f"Ten'Up {club_name}",
            manufacturer="FFT",
            model="Ten'Up club",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"https://tenup.fft.fr/club/{club_code}/reservations",
        )

    @property
    def club_code(self) -> str:
        return self.coordinator.entry.data[CONF_CLUB_CODE]
