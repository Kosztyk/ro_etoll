"""Poll eToll without representing failed requests as negative/zero values."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RoEtollAPI
from .const import (
    CONF_ISTORIC_TRANZACTII,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ISTORIC_TRANZACTII_DEFAULT,
)
from .exceptions import RoEtollAuthError, RoEtollError
from .helpers import section_status

_LOGGER = logging.getLogger(__name__)


class RoEtollCoordinator(DataUpdateCoordinator[dict]):
    """An account's current profile, registered vehicles and verification data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: RoEtollAPI,
        config_entry: ConfigEntry,
        update_interval: int = DEFAULT_UPDATE_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_coordinator",
            update_interval=timedelta(seconds=update_interval),
            config_entry=config_entry,
        )
        self.api = api
        self._countries: list[dict] | None = None

    async def _async_update_data(self) -> dict:
        try:
            return await self._fetch_all_data()
        except RoEtollAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except RoEtollError as err:
            raise UpdateFailed(str(err)) from err

    async def _fetch_all_data(self) -> dict:
        # These must succeed. A failed vehicle list must never remove entities.
        profile = await self.api.get_profile()
        vehicles = await self.api.get_vehicles()
        failures: list[str] = []

        if self._countries is None:
            try:
                self._countries = await self.api.get_countries()
            except RoEtollAuthError:
                raise
            except RoEtollError as err:
                _LOGGER.debug("Country lookup unavailable: %s", err)
                failures.append("countries")

        verification: dict[str, dict | None] = {}
        verification_errors: dict[str, dict[str, dict]] = {}
        bridge_fallbacks: dict[str, dict] = {}
        for vehicle in vehicles:
            vehicle_id = str(vehicle["id"])
            # The browser's ForType request contains exactly one service type.
            # Keep a working vignette result even when bridge verification fails.
            result = {"vehicle": {"vehicleId": vehicle_id}}
            errors = {}
            for section in ("vignette", "bridge"):
                try:
                    response = await self.api.verify_vehicle(
                        vehicle_id, section.upper()
                    )
                    result[section] = response[section]
                except RoEtollAuthError:
                    raise
                except RoEtollError as err:
                    _LOGGER.debug("%s verification unavailable: %s", section, err)
                    result[section] = None
                    errors[section] = {
                        "kind": type(err).__name__,
                        "http_status": getattr(err, "http_status", None),
                    }
                    failures.append(f"verification.{section}")
            if section_status(result, "bridge") == "UNAVAILABLE":
                bridge_fallbacks[vehicle_id] = await self._bridge_fallback(
                    vehicle, result, failures
                )
            verification[vehicle_id] = (
                result
                if result.get("vignette") is not None
                or result.get("bridge") is not None
                else None
            )
            if errors:
                verification_errors[vehicle_id] = errors

        years = self.config_entry.options.get(
            CONF_ISTORIC_TRANZACTII, ISTORIC_TRANZACTII_DEFAULT
        )
        now = datetime.now(timezone.utc)
        try:
            invoices = await self.api.get_invoices(
                now - timedelta(days=years * 365), now
            )
        except RoEtollAuthError:
            raise
        except RoEtollError as err:
            _LOGGER.debug("Invoice lookup unavailable: %s", err)
            invoices = None
            failures.append("invoices")

        # Detect a profile change during polling rather than mix two profiles.
        final_profile = await self.api.get_profile()
        if final_profile.get("id") != profile.get("id"):
            raise UpdateFailed(
                "The eToll current profile changed during polling; retrying next update."
            )
        if failures:
            _LOGGER.warning(
                "Some eToll data is unavailable: %s", ", ".join(sorted(set(failures)))
            )
        return {
            "profile": profile,
            "vehicles": vehicles,
            "verification": verification,
            "verification_errors": verification_errors,
            "bridge_fallbacks": bridge_fallbacks,
            "countries": self._countries or [],
            "invoices": invoices,
            "failed_sections": sorted(set(failures)),
        }

    async def _bridge_fallback(
        self, vehicle: dict, result: dict, failures: list[str]
    ) -> dict:
        """Try one typed lookup only after an explicit saved-vehicle UNAVAILABLE."""
        if not all(
            isinstance(vehicle.get(key), str) and vehicle[key].strip()
            for key in ("plateNumber", "countryCode")
        ):
            return {"status": "MISSING_IDENTIFICATION", "used": False}
        try:
            response = await self.api.verify_bridge_by_plate(vehicle)
        except RoEtollAuthError:
            raise
        except RoEtollError as err:
            _LOGGER.debug("Bridge plate lookup unavailable: %s", err)
            failures.append("verification.bridge_fallback")
            return {
                "status": "REQUEST_FAILED",
                "used": False,
                "kind": type(err).__name__,
                "http_status": getattr(err, "http_status", None),
            }
        status = section_status(response, "bridge")
        used = status == "OK"
        if used:
            result["bridge"] = response["bridge"]
        return {"status": status, "used": used}
