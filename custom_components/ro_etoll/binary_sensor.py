"""Expiry warnings and data freshness, evaluated without extra HTTP requests."""

from datetime import datetime, timedelta, timezone

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import callback

from .const import (
    CONF_EXPIRY_WARNING_DAYS,
    CONF_STALE_AFTER_HOURS,
    DATA_SOURCES,
    DEFAULT_EXPIRY_WARNING_DAYS,
    DEFAULT_STALE_AFTER_HOURS,
    DOMAIN,
)
from .entity import RoEtollEntity
from .helpers import parse_datetime, section_items, select_vignette, vignette_active


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    coordinator = config_entry.runtime_data
    async_add_entities(
        [
            StaleDataSensor(
                coordinator,
                config_entry,
                f"{DOMAIN}_stale_{source}_{config_entry.entry_id}",
                source,
            )
            for source in DATA_SOURCES
        ]
    )
    added = set()

    @callback
    def add_vehicles() -> None:
        entities = []
        for vehicle in (coordinator.data or {}).get("vehicles", []):
            identifier = str(vehicle["id"])
            if identifier not in added:
                added.add(identifier)
                entities.append(
                    ExpiryWarningSensor(
                        coordinator,
                        config_entry,
                        f"{DOMAIN}_expiry_warning_{identifier}_{config_entry.entry_id}",
                        identifier,
                        vehicle["plateNumber"],
                    )
                )
        if entities:
            async_add_entities(entities)

    add_vehicles()
    config_entry.async_on_unload(coordinator.async_add_listener(add_vehicles))


class ExpiryWarningSensor(RoEtollEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:calendar-alert"

    def __init__(self, coordinator, entry, uid, vehicle_id, plate):
        super().__init__(coordinator, entry, uid)
        self._vehicle_id = vehicle_id
        self._attr_name = f"Rovinietă expiră curând ({plate})"

    @property
    def vehicle(self) -> dict | None:
        return next(
            (
                v
                for v in (self.coordinator.data or {}).get("vehicles", [])
                if str(v["id"]) == self._vehicle_id
            ),
            None,
        )

    @property
    def warning_days(self) -> int:
        return self._config_entry.options.get(
            CONF_EXPIRY_WARNING_DAYS, DEFAULT_EXPIRY_WARNING_DAYS
        )

    @property
    def is_on(self) -> bool | None:
        if self.vehicle is None:
            return None
        now = datetime.now(timezone.utc)
        verification = (
            (self.coordinator.data or {}).get("verification", {}).get(self._vehicle_id)
        )
        items = section_items(verification, "vignette")
        active = vignette_active(items, now)
        if active is not True:
            # An expiry date alone does not prove current validity.
            return active
        selected = select_vignette(items, now) or {}
        raw_end = selected.get("validityEndDate")
        end = parse_datetime(raw_end, end_of_day=True)
        if raw_end is None:
            eligibility = self.vehicle.get("vignetteEligibility")
            if isinstance(eligibility, dict):
                end = parse_datetime(
                    eligibility.get("expirationDateCurrentVignette"), end_of_day=True
                )
        if end is None:
            return None
        return timedelta(0) <= end - now <= timedelta(days=self.warning_days)

    @property
    def available(self) -> bool:
        return super().available and self.vehicle is not None and self.is_on is not None

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "Prag avertizare (zile)": self.warning_days,
            "Acoperire": "Rovinieta activă care expiră în intervalul configurat; nu include roviniete deja expirate sau viitoare.",
        }


class StaleDataSensor(RoEtollEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:database-clock"

    def __init__(self, coordinator, entry, uid, source):
        super().__init__(coordinator, entry, uid)
        self.source = source
        self._attr_name = f"Date învechite ({DATA_SOURCES[source]})"

    @property
    def available(self) -> bool:
        # Failed coordinator updates are exactly when this diagnostic is useful.
        return True

    @property
    def stale_hours(self) -> int:
        return self._config_entry.options.get(
            CONF_STALE_AFTER_HOURS, DEFAULT_STALE_AFTER_HOURS
        )

    @property
    def is_on(self) -> bool:
        last = self.coordinator.source_last_success.get(self.source)
        return last is None or datetime.now(timezone.utc) - last > timedelta(
            hours=self.stale_hours
        )

    @property
    def extra_state_attributes(self) -> dict:
        last = self.coordinator.source_last_success.get(self.source)
        return {
            "Prag vechime (ore)": self.stale_hours,
            "Ultima actualizare reușită": last.isoformat() if last else None,
            "Date primite de la pornire": last is not None,
            "Ultima citire reușită": self.coordinator.source_status.get(
                self.source, False
            ),
        }
