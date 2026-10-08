"""Account summaries and per-source diagnostics for ro_etoll."""

from collections import Counter
from datetime import datetime, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory

from .const import DATA_SOURCES, MAX_ATTR_TRECERI
from .entity import RoEtollEntity
from .helpers import (
    invoice_amount,
    invoice_period_total,
    latest_record,
    numeric,
    parse_datetime,
    period_start,
    purchase_date,
    purchased_services,
)


class AccountSourceSensor(RoEtollEntity, SensorEntity):
    source_key: str

    @property
    def records(self):
        return (self.coordinator.data or {}).get(self.source_key)

    @property
    def available(self) -> bool:
        return super().available and self.records is not None


class VehicleCountSensor(AccountSourceSensor):
    source_key = "vehicles"
    _attr_name = "Vehicule înregistrate"
    _attr_icon = "mdi:car-multiple"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        return len(self.records) if self.records is not None else None

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "Acoperire": "Vehiculele de tip CAR din profilul curent, toate paginile; fără remorci."
        }


class NotificationCountSensor(AccountSourceSensor):
    source_key = "notification_count"
    _attr_name = "Notificări eToll"
    _attr_icon = "mdi:bell-badge"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        return self.records

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "Acoperire": "Numărul raportat de sumarul eToll; nu este interpretat ca număr de notificări necitite.",
            "Sursă": "/api/notifications/summary",
        }


class LatestNotificationSensor(AccountSourceSensor):
    source_key = "notifications"
    _attr_name = "Ultima notificare"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:bell-clock"

    @property
    def selected(self) -> dict | None:
        return latest_record(self.records, "createdAt")

    @property
    def available(self) -> bool:
        return super().available and (not self.records or self.selected is not None)

    @property
    def native_value(self) -> datetime | None:
        return parse_datetime((self.selected or {}).get("createdAt"))

    @property
    def extra_state_attributes(self) -> dict:
        item = self.selected or {}
        message = item.get("description")
        return {
            "Notificare disponibilă": bool(item),
            "Mesaj": message[:2000] if isinstance(message, str) else None,
            "Tip": item.get("type"),
            "Stare în portal": item.get("status"),
            "Număr de înmatriculare": item.get("vehiclePlateNumber"),
        }


class InvoiceTotalSensor(AccountSourceSensor):
    source_key = "invoices"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "RON"
    _attr_suggested_display_precision = 2
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:cash-multiple"

    def __init__(self, coordinator, entry, uid, period):
        super().__init__(coordinator, entry, uid)
        self.period = period
        self._attr_name = (
            "Total facturi luna aceasta"
            if period == "month"
            else "Total facturi anul acesta"
        )

    @property
    def native_value(self):
        return invoice_period_total(
            self.records, datetime.now(timezone.utc), self.period
        )

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def last_reset(self) -> datetime:
        return period_start(datetime.now(timezone.utc), self.period)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "Început perioadă": self.last_reset.isoformat(),
            "Grupare": "Data plății; fus orar Europe/Bucharest",
            "Acoperire": "Facturile returnate pentru profilul curent eToll",
        }


class LatestInvoiceSensor(AccountSourceSensor):
    source_key = "invoices"
    _attr_name = "Ultima factură"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "RON"
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:receipt-text"

    @property
    def selected(self) -> dict | None:
        return latest_record(self.records, "paymentDate")

    @property
    def native_value(self):
        return invoice_amount(self.selected) if self.selected else None

    @property
    def available(self) -> bool:
        return super().available and (not self.records or self.native_value is not None)

    @property
    def extra_state_attributes(self) -> dict:
        invoice = self.selected or {}
        date = parse_datetime(invoice.get("paymentDate"))
        return {
            "Factură disponibilă": bool(invoice),
            "Număr factură": invoice.get("externalNumber"),
            "Serie factură": invoice.get("externalSeries"),
            "Data plății": date.isoformat() if date else None,
            "Metodă de plată": invoice.get("paymentMethod"),
        }


class PurchasedServicesSensor(AccountSourceSensor):
    source_key = "services"
    _attr_name = "Servicii cumpărate"
    _attr_icon = "mdi:receipt-text-check"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def purchases(self) -> list[dict] | None:
        return purchased_services(self.records)

    @property
    def native_value(self) -> int | None:
        return len(self.purchases) if self.purchases is not None else None

    @property
    def available(self) -> bool:
        return super().available and self.purchases is not None

    @property
    def extra_state_attributes(self) -> dict:
        details = []
        for item in (self.purchases or [])[:MAX_ATTR_TRECERI]:
            price = item.get("price")
            amount = (
                numeric(price.get("totalPrice"))
                if isinstance(price, dict)
                else numeric(price)
            )
            details.append(
                {
                    "Tip": item.get("type"),
                    "Stare": item.get("status"),
                    "Preț RON": float(amount) if amount is not None else None,
                    "Valabil de la": item.get("validFrom"),
                    "Valabil până la": item.get("validUntil"),
                }
            )
        return {
            "Stări incluse": "ACTIVE, CONSUMED, EXPIRED",
            "Stări returnate": dict(
                Counter(item.get("status") for item in self.records or [])
            ),
            "Detalii": details,
            "Detalii afișate": len(details),
            "Acoperire": "Servicii ale profilului curent; nu confirmă valabilitatea rovinietei sau soldul peajelor.",
        }


class LatestPurchaseSensor(PurchasedServicesSensor):
    _attr_name = "Ultima achiziție"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_state_class = None
    _attr_icon = "mdi:cart-clock"

    @property
    def selected(self) -> dict | None:
        items = self.purchases
        if not items:
            return None
        dates = [purchase_date(item) for item in items]
        if any(date is None for date in dates):
            return None
        return items[max(range(len(items)), key=lambda index: dates[index])]

    @property
    def native_value(self) -> datetime | None:
        return purchase_date(self.selected) if self.selected else None

    @property
    def available(self) -> bool:
        return super().available and (not self.purchases or self.selected is not None)

    @property
    def extra_state_attributes(self) -> dict:
        item = self.selected or {}
        price = item.get("price")
        amount = (
            numeric(price.get("totalPrice"))
            if isinstance(price, dict)
            else numeric(price)
        )
        return {
            "Achiziție disponibilă": bool(item),
            "Tip": item.get("type"),
            "Stare": item.get("status"),
            "Preț RON": float(amount) if amount is not None else None,
            "Valabil de la": item.get("validFrom"),
            "Valabil până la": item.get("validUntil"),
        }


class SourceUpdateSensor(RoEtollEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:update"

    def __init__(self, coordinator, entry, uid, source):
        super().__init__(coordinator, entry, uid)
        self.source = source
        self._attr_name = f"Ultima actualizare reușită ({DATA_SOURCES[source]})"

    @property
    def available(self) -> bool:
        # Retain diagnostic visibility when the next account refresh fails.
        return True

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.source_last_success.get(self.source)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "Ultima citire reușită": self.coordinator.source_status.get(
                self.source, False
            ),
            "Acoperire": "De la pornirea integrării, pentru profilul curent",
        }
