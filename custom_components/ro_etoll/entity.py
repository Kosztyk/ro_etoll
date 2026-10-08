"""Shared account device for ro_etoll entities."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, PORTAL_URL, VERSION
from .coordinator import RoEtollCoordinator


class RoEtollEntity(CoordinatorEntity[RoEtollCoordinator]):
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self, coordinator: RoEtollCoordinator, entry: ConfigEntry, uid: str
    ) -> None:
        super().__init__(coordinator)
        self._config_entry = entry
        self._attr_unique_id = uid

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name="ro_etoll",
            manufacturer="Kosztyk",
            model="ro_etoll",
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=PORTAL_URL,
        )
