"""Counts and integration settings only; omit all account/vehicle identifiers."""

from collections import Counter

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_ISTORIC_TRANZACTII, CONF_UPDATE_INTERVAL, DOMAIN, VERSION
from .helpers import section_items, section_status


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    data = (coordinator.data or {}) if coordinator else {}
    verification = list(data.get("verification", {}).values())
    invoices = data.get("invoices")
    return {
        "integration_version": VERSION,
        "config_version": entry.version,
        "last_update_success": coordinator.last_update_success
        if coordinator
        else False,
        "settings": {
            key: entry.options.get(key)
            for key in (CONF_UPDATE_INTERVAL, CONF_ISTORIC_TRANZACTII)
        },
        "counts": {
            "vehicles": len(data.get("vehicles", [])),
            "vignette_verification_available": sum(
                section_items(v, "vignette") is not None for v in verification
            ),
            "bridge_verification_available": sum(
                section_items(v, "bridge") is not None for v in verification
            ),
            "invoices": len(invoices) if invoices is not None else None,
        },
        "failed_sections": data.get("failed_sections", []),
        "verification_status_counts": {
            section: dict(
                Counter(section_status(value, section) for value in verification)
            )
            for section in ("vignette", "bridge")
        },
        "verification_error_counts": {
            section: dict(
                Counter(
                    errors[section]["kind"]
                    + (
                        f" (HTTP {errors[section]['http_status']})"
                        if errors[section]["http_status"] is not None
                        else ""
                    )
                    for errors in data.get("verification_errors", {}).values()
                    if section in errors
                )
            )
            for section in ("vignette", "bridge")
        },
        "bridge_fallback_counts": dict(
            Counter(
                value["status"] for value in data.get("bridge_fallbacks", {}).values()
            )
        ),
        "bridge_fallback_used": sum(
            bool(value.get("used"))
            for value in data.get("bridge_fallbacks", {}).values()
        ),
        "bridge_fallback_error_counts": dict(
            Counter(
                value["kind"]
                + (
                    f" (HTTP {value['http_status']})"
                    if value.get("http_status")
                    else ""
                )
                for value in data.get("bridge_fallbacks", {}).values()
                if value.get("kind")
            )
        ),
    }
