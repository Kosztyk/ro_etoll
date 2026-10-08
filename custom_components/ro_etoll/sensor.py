"""ro_etoll sensors backed by verified portal responses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import ClassVar

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .account_sensors import (
    InvoiceTotalSensor,
    LatestInvoiceSensor,
    LatestNotificationSensor,
    LatestPurchaseSensor,
    NotificationCountSensor,
    PurchasedServicesSensor,
    SourceUpdateSensor,
    VehicleCountSensor,
)
from .const import (
    CONF_ISTORIC_TRANZACTII,
    DATA_SOURCES,
    DOMAIN,
    ISTORIC_TRANZACTII_DEFAULT,
    MAX_ATTR_TRECERI,
    PORTAL_URL,
)
from .coordinator import RoEtollCoordinator
from .entity import RoEtollEntity
from .helpers import (
    bridge_balance,
    bridge_crossings,
    item_active,
    next_vignette,
    numeric,
    parse_datetime,
    sanitize_plate_no,
    section_items,
    section_status,
    select_vignette,
    vignette_active,
)

VERIFICATION_LABELS = {
    "OK": "Disponibilă",
    "UNAVAILABLE": "Indisponibilă la eToll",
    "REQUEST_FAILED": "Cerere eșuată",
    "MISSING_SECTION": "Secțiune lipsă",
    "INVALID_RESPONSE": "Răspuns invalid",
    "UNKNOWN_STATUS": "Stare necunoscută",
    "INCOMPLETE_DATA": "Date incomplete",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RoEtollCoordinator = config_entry.runtime_data
    registry = er.async_get(hass)
    existing = er.async_entries_for_config_entry(registry, config_entry.entry_id)
    claimed: set[str] = set()

    def unique_id(
        kind: str, plate: str | None = None, vehicle_id: str | None = None
    ) -> str:
        prefix, suffix = f"{DOMAIN}_{kind}_", f"_{config_entry.entry_id}"
        for entity in existing:
            uid = entity.unique_id
            if (
                entity.domain != "sensor"
                or uid in claimed
                or not (uid.startswith(prefix) and uid.endswith(suffix))
            ):
                continue
            middle = uid[len(prefix) : -len(suffix)]
            if (
                plate is None
                or middle.replace("_", "").casefold()
                == plate.replace(" ", "").casefold()
            ):
                claimed.add(uid)
                return uid
        result = (
            f"{prefix}{sanitize_plate_no(plate)}{suffix}"
            if plate
            else f"{prefix}{config_entry.entry_id}"
        )
        if result in claimed:
            result = f"{prefix}{sanitize_plate_no(plate or '')}_{vehicle_id}{suffix}"
        claimed.add(result)
        return result

    async_add_entities(
        [
            DateUtilizatorSensor(
                coordinator, config_entry, unique_id("date_utilizator")
            ),
            RaportTranzactiiSensor(
                coordinator, config_entry, unique_id("raport_tranzactii")
            ),
            VehicleCountSensor(coordinator, config_entry, unique_id("vehicle_count")),
            NotificationCountSensor(
                coordinator, config_entry, unique_id("notification_count")
            ),
            LatestNotificationSensor(
                coordinator, config_entry, unique_id("latest_notification")
            ),
            InvoiceTotalSensor(
                coordinator, config_entry, unique_id("invoice_month"), "month"
            ),
            InvoiceTotalSensor(
                coordinator, config_entry, unique_id("invoice_year"), "year"
            ),
            LatestInvoiceSensor(coordinator, config_entry, unique_id("latest_invoice")),
            PurchasedServicesSensor(
                coordinator, config_entry, unique_id("purchased_services")
            ),
            LatestPurchaseSensor(
                coordinator, config_entry, unique_id("latest_purchase")
            ),
            *[
                SourceUpdateSensor(
                    coordinator,
                    config_entry,
                    unique_id(f"last_success_{source}"),
                    source,
                )
                for source in DATA_SOURCES
            ],
        ]
    )
    added: set[str] = set()

    @callback
    def add_vehicles() -> None:
        entities = []
        for vehicle in (coordinator.data or {}).get("vehicles", []):
            vehicle_id, plate = str(vehicle["id"]), vehicle["plateNumber"]
            if vehicle_id in added:
                continue
            added.add(vehicle_id)
            for kind, cls in (
                ("vehicul", VehiculSensor),
                ("expirare_rovinieta", VignetteExpirySensor),
                ("zile_rovinieta", VignetteDaysSensor),
                ("urmatoarea_rovinieta", NextVignetteSensor),
                ("stare_verificare_peaje", BridgeVerificationStatusSensor),
                ("treceri_pod", TreceriPodSensor),
                ("sold_peaje_neexpirate", SoldSensor),
                ("plata_treceri_pod", PlataTreceriPodSensor),
            ):
                entities.append(
                    cls(
                        coordinator,
                        config_entry,
                        unique_id(kind, plate, vehicle_id),
                        vehicle_id,
                        plate,
                    )
                )
        if entities:
            async_add_entities(entities)

    add_vehicles()
    config_entry.async_on_unload(coordinator.async_add_listener(add_vehicles))


class RoEtollBaseSensor(RoEtollEntity, SensorEntity):
    """Sensor attached to the integration's account device."""


class DateUtilizatorSensor(RoEtollBaseSensor):
    _attr_name = "Date utilizator"
    _attr_icon = "mdi:account-details"

    @property
    def native_value(self) -> str | None:
        profile = (self.coordinator.data or {}).get("profile", {})
        for key in ("name", "email", "id"):
            value = profile.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:255]
        return None

    @property
    def extra_state_attributes(self) -> dict:
        profile = (self.coordinator.data or {}).get("profile", {})
        return {
            "ID profil": profile.get("id"),
            "Numele și prenumele": profile.get("name"),
            "Email utilizator": profile.get("email"),
            "Profil curent": profile.get("isCurrent"),
            "Portal": PORTAL_URL,
        }


class VehicleSensor(RoEtollBaseSensor):
    def __init__(
        self,
        coordinator: RoEtollCoordinator,
        entry: ConfigEntry,
        uid: str,
        vehicle_id: str,
        plate: str,
    ) -> None:
        super().__init__(coordinator, entry, uid)
        self._vehicle_id, self._plate = vehicle_id, plate
        self._attr_name = f"{self.label} ({plate})"

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

    def items(self, section: str) -> list[dict] | None:
        return section_items(
            (self.coordinator.data or {}).get("verification", {}).get(self._vehicle_id),
            section,
        )

    def verification_status(self, section: str) -> str:
        return section_status(
            (self.coordinator.data or {}).get("verification", {}).get(self._vehicle_id),
            section,
        )

    def verification_attributes(self, section: str) -> dict:
        status = self.verification_status(section)
        error = (
            (self.coordinator.data or {})
            .get("verification_errors", {})
            .get(self._vehicle_id, {})
            .get(section, {})
        )
        attrs = {
            "Stare verificare": VERIFICATION_LABELS[status],
            "Cod stare verificare": status,
            "Sursă verificare": "POST /api/tolls/verification",
        }
        if error:
            attrs["Tip eroare"] = error.get("kind")
            attrs["Cod HTTP"] = error.get("http_status")
        if section == "bridge":
            fallback = (
                (self.coordinator.data or {})
                .get("bridge_fallbacks", {})
                .get(self._vehicle_id)
            )
            attrs["Metodă verificare"] = (
                "Număr de înmatriculare și țară"
                if fallback and fallback.get("used")
                else "ID vehicul salvat"
            )
            if fallback:
                status = fallback["status"]
                attrs["Verificare alternativă după număr"] = (
                    "Date vehicul incomplete"
                    if status == "MISSING_IDENTIFICATION"
                    else VERIFICATION_LABELS[status]
                )
                attrs["Cod verificare alternativă"] = status
                if fallback.get("kind"):
                    attrs["Tip eroare verificare alternativă"] = fallback["kind"]
                    attrs["Cod HTTP verificare alternativă"] = fallback.get(
                        "http_status"
                    )
            if self.verification_status("bridge") == "UNAVAILABLE":
                attrs["Explicație"] = (
                    "eToll nu a furnizat date despre peaje. "
                    "Indisponibil nu înseamnă sold zero sau lipsa trecerilor."
                )
        return attrs

    def vignette_expiry_info(self, now: datetime) -> tuple[datetime | None, str | None]:
        """Prefer verification, then the explicit current-expiry field on vehicles."""
        items = self.items("vignette")
        if items is not None:
            vignette = select_vignette(items, now)
            if vignette is None:
                # A verified empty result overrides eligibility metadata.
                return None, None
            raw_end = vignette.get("validityEndDate")
            end = parse_datetime(raw_end, end_of_day=True)
            if end is not None:
                return end, "Verificare rovinietă eToll"
            if raw_end is not None or item_active(vignette, now) is not True:
                # Do not hide malformed dates or mix a future vignette with current metadata.
                return None, None
        eligibility = (self.vehicle or {}).get("vignetteEligibility")
        if not isinstance(eligibility, dict):
            return None, None
        end = parse_datetime(
            eligibility.get("expirationDateCurrentVignette"), end_of_day=True
        )
        return end, "Eligibilitate vehicul eToll" if end else None

    def vignette_expiry(self, now: datetime) -> datetime | None:
        return self.vignette_expiry_info(now)[0]

    def expiry_attributes(self) -> dict:
        _, source = self.vignette_expiry_info(datetime.now(timezone.utc))
        return {
            **self.verification_attributes("vignette"),
            "Sursă dată expirare": source,
        }

    @property
    def available(self) -> bool:
        return super().available and self.vehicle is not None

    def vehicle_attributes(self) -> dict:
        vehicle = self.vehicle or {}
        country = vehicle.get("countryCode")
        name = next(
            (
                c.get("ro")
                for c in (self.coordinator.data or {}).get("countries", [])
                if c.get("countryCode") == country
            ),
            None,
        )
        return {
            "Număr de înmatriculare": vehicle.get("plateNumber", self._plate),
            "VIN": vehicle.get("vin"),
            "Seria certificatului": vehicle.get("registrationSerial"),
            "Țara": name or country,
            "Categorie vehicul": vehicle.get("category"),
            "Normă de emisii": vehicle.get("emissionStandard"),
            "MTMA": vehicle.get("mtma"),
            "Tip vehicul": vehicle.get("vehicleType"),
        }


class VehiculSensor(VehicleSensor):
    label = "Rovinietă activă"
    _attr_icon = "mdi:car"

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> str | None:
        active = vignette_active(self.items("vignette"), datetime.now(timezone.utc))
        return None if active is None else ("Da" if active else "Nu")

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {
            **self.vehicle_attributes(),
            **self.verification_attributes("vignette"),
        }
        items = self.items("vignette")
        if items is None:
            return attrs
        now = datetime.now(timezone.utc)
        vignette = select_vignette(items, now)
        attrs["Număr roviniete"] = len(items)
        if vignette is None:
            attrs["Rovinietă"] = "Nu există rovinietă"
            return attrs
        start = parse_datetime(vignette.get("validityStartDate"))
        end = parse_datetime(vignette.get("validityEndDate"), end_of_day=True)
        attrs.update(
            {
                "Categorie vignietă": vignette.get("vehicleCategory"),
                "Data început vignietă": start.isoformat() if start else None,
                "Data sfârșit vignietă": end.isoformat() if end else None,
                "Expiră peste (zile)": (end - now).days if end else None,
                "Serie rovinietă": vignette.get("series"),
                "Rovinietă din sistemul anterior": vignette.get("fromSiegmcr"),
                "Stare rovinietă selectată": "Viitoare"
                if start and start > now
                else self.native_value,
            }
        )
        return attrs


class VignetteExpirySensor(VehicleSensor):
    """Expose the selected verified vignette's expiry as a visible timestamp."""

    label = "Expirare rovinietă"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-end"

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> datetime | None:
        return self.vignette_expiry(datetime.now(timezone.utc))

    @property
    def extra_state_attributes(self) -> dict:
        return self.expiry_attributes()


class VignetteDaysSensor(VehicleSensor):
    """Expose the existing expiry-day attribute as a numeric sensor."""

    label = "Zile până la expirare rovinietă"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_icon = "mdi:calendar-clock"

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> int | None:
        now = datetime.now(timezone.utc)
        end = self.vignette_expiry(now)
        return (end - now).days if end else None

    @property
    def extra_state_attributes(self) -> dict:
        return self.expiry_attributes()


class NextVignetteSensor(VehicleSensor):
    """Start of an actual future vignette, never an eligibility interval."""

    label = "Început următoare rovinietă"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-start"

    @property
    def selected(self) -> dict | None:
        return next_vignette(self.items("vignette"), datetime.now(timezone.utc))

    @property
    def available(self) -> bool:
        items = self.items("vignette")
        return (
            super().available
            and items is not None
            and all(
                parse_datetime(item.get("validityStartDate")) is not None
                and parse_datetime(item.get("validityEndDate"), end_of_day=True)
                is not None
                for item in items
            )
        )

    @property
    def native_value(self) -> datetime | None:
        return parse_datetime((self.selected or {}).get("validityStartDate"))

    @property
    def extra_state_attributes(self) -> dict:
        item = self.selected or {}
        end = parse_datetime(item.get("validityEndDate"), end_of_day=True)
        return {
            **self.verification_attributes("vignette"),
            "Rovinietă viitoare disponibilă": bool(item),
            "Data expirării": end.isoformat() if end else None,
            "Serie rovinietă": item.get("series"),
        }


class BridgeVerificationStatusSensor(VehicleSensor):
    """Explain missing bridge readings without inventing a balance."""

    label = "Stare verificare peaje"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options: ClassVar[list[str]] = list(VERIFICATION_LABELS.values())
    _attr_icon = "mdi:bridge"

    @property
    def native_value(self) -> str:
        status = self.verification_status("bridge")
        if status == "OK":
            items = self.items("bridge")
            if (
                bridge_balance(items, datetime.now(timezone.utc)) is None
                or bridge_crossings(items) is None
            ):
                status = "INCOMPLETE_DATA"
        return VERIFICATION_LABELS[status]

    @property
    def extra_state_attributes(self) -> dict:
        items = self.items("bridge")
        return {
            **self.verification_attributes("bridge"),
            "Peaje returnate": len(items) if items is not None else None,
            "Sold disponibil": bridge_balance(items, datetime.now(timezone.utc))
            is not None,
            "Istoric treceri disponibil": bridge_crossings(items) is not None,
        }


class PlataTreceriPodSensor(VehicleSensor):
    """Explain unsupported unpaid detection without reporting a debt balance."""

    label = "Restanțe treceri pod"
    _attr_icon = "mdi:invoice-text-remove"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = ["Nesuportat de API"]

    @property
    def native_value(self) -> str:
        return "Nesuportat de API"

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "Număr de înmatriculare": self._plate,
            "Stare verificare": "API-ul eToll verificat nu expune detecțiile neplătite din vechiul portal.",
        }


class TreceriPodSensor(VehicleSensor):
    label = "Treceri pod"
    _attr_icon = "mdi:bridge"

    def crossings(self) -> list[dict] | None:
        return bridge_crossings(self.items("bridge"))

    @property
    def available(self) -> bool:
        return super().available and self.crossings() is not None

    @property
    def native_value(self) -> int | None:
        crossings = self.crossings()
        return len(crossings) if crossings is not None else None

    @property
    def extra_state_attributes(self) -> dict:
        crossings = sorted(
            self.crossings() or [],
            key=lambda c: str(c.get("crossingTime") or ""),
            reverse=True,
        )
        return {
            **self.vehicle_attributes(),
            **self.verification_attributes("bridge"),
            "Număr total treceri": self.native_value,
            "Treceri afișate": min(len(crossings), MAX_ATTR_TRECERI),
            "Detalii": [
                {
                    "Timp detectare": c.get("crossingTime"),
                    "Direcție": c.get("direction"),
                }
                for c in crossings[:MAX_ATTR_TRECERI]
            ],
            "Acoperire": "Treceri returnate de verificarea peajelor; nu include detecții neplătite.",
        }


class SoldSensor(VehicleSensor):
    label = "Sold peaje neexpirate"
    _attr_icon = "mdi:boom-gate"
    _attr_native_unit_of_measurement = "treceri"

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> int | float | None:
        return bridge_balance(self.items("bridge"), datetime.now(timezone.utc))

    @property
    def extra_state_attributes(self) -> dict:
        return {
            **self.verification_attributes("bridge"),
            "Sold peaje neexpirate": self.native_value,
            "Unitate": "treceri",
            "Număr de înmatriculare": self._plate,
        }


class RaportTranzactiiSensor(RoEtollBaseSensor):
    _attr_name = "Raport tranzacții"
    _attr_icon = "mdi:chart-bar-stacked"

    @property
    def available(self) -> bool:
        return (
            super().available
            and (self.coordinator.data or {}).get("invoices") is not None
        )

    @property
    def native_value(self) -> int | None:
        invoices = (self.coordinator.data or {}).get("invoices")
        return len(invoices) if invoices is not None else None

    @property
    def extra_state_attributes(self) -> dict:
        invoices = (self.coordinator.data or {}).get("invoices")
        amounts = (
            [
                numeric(
                    invoice["total"].get("totalPrice")
                    if isinstance(invoice.get("total"), dict)
                    else invoice.get("total")
                )
                for invoice in invoices
            ]
            if invoices is not None
            else []
        )
        total = sum(amounts) if invoices is not None and None not in amounts else None
        years = self._config_entry.options.get(
            CONF_ISTORIC_TRANZACTII, ISTORIC_TRANZACTII_DEFAULT
        )
        return {
            "Perioadă analizată": f"Ultimii {years} ani",
            "Număr facturi": self.native_value,
            "Suma totală plătită": f"{total:.2f} RON" if total is not None else None,
            "Sursă": "Facturile profilului curent eToll",
        }
