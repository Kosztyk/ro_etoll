"""ro_etoll account setup, reauthentication and polling options."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import RoEtollAPI
from .const import (
    CONF_EXPIRY_WARNING_DAYS,
    CONF_ISTORIC_TRANZACTII,
    CONF_PASSWORD,
    CONF_STALE_AFTER_HOURS,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    DEFAULT_EXPIRY_WARNING_DAYS,
    DEFAULT_STALE_AFTER_HOURS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ISTORIC_TRANZACTII_DEFAULT,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
)
from .exceptions import (
    RoEtollApiError,
    RoEtollAuthError,
    RoEtollAuthUnsupported,
    RoEtollConnectionError,
    RoEtollProfileError,
)

USERNAME = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
INTERVAL = NumberSelector(
    NumberSelectorConfig(
        min=MIN_UPDATE_INTERVAL,
        max=MAX_UPDATE_INTERVAL,
        step=1,
        unit_of_measurement="s",
        mode=NumberSelectorMode.BOX,
    )
)
HISTORY = NumberSelector(
    NumberSelectorConfig(min=1, max=10, step=1, mode=NumberSelectorMode.BOX)
)


def options_schema(options: Mapping[str, Any]) -> dict:
    return {
        vol.Required(
            CONF_UPDATE_INTERVAL,
            default=options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        ): INTERVAL,
        vol.Required(
            CONF_ISTORIC_TRANZACTII,
            default=options.get(CONF_ISTORIC_TRANZACTII, ISTORIC_TRANZACTII_DEFAULT),
        ): HISTORY,
        vol.Required(
            CONF_EXPIRY_WARNING_DAYS,
            default=options.get(CONF_EXPIRY_WARNING_DAYS, DEFAULT_EXPIRY_WARNING_DAYS),
        ): NumberSelector(
            NumberSelectorConfig(min=1, max=365, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Required(
            CONF_STALE_AFTER_HOURS,
            default=options.get(CONF_STALE_AFTER_HOURS, DEFAULT_STALE_AFTER_HOURS),
        ): NumberSelector(
            NumberSelectorConfig(min=1, max=168, step=1, mode=NumberSelectorMode.BOX)
        ),
    }


def validate_options(values: dict) -> tuple[dict, dict]:
    clean, errors = {}, {}
    for key, low, high, default, error in (
        (
            CONF_UPDATE_INTERVAL,
            MIN_UPDATE_INTERVAL,
            MAX_UPDATE_INTERVAL,
            DEFAULT_UPDATE_INTERVAL,
            "invalid_update_interval",
        ),
        (CONF_ISTORIC_TRANZACTII, 1, 10, ISTORIC_TRANZACTII_DEFAULT, "invalid_history"),
        (
            CONF_EXPIRY_WARNING_DAYS,
            1,
            365,
            DEFAULT_EXPIRY_WARNING_DAYS,
            "invalid_warning_days",
        ),
        (
            CONF_STALE_AFTER_HOURS,
            1,
            168,
            DEFAULT_STALE_AFTER_HOURS,
            "invalid_stale_hours",
        ),
    ):
        value = values.get(key, default)
        try:
            integer = int(value)
            if (
                isinstance(value, bool)
                or integer != float(value)
                or not low <= integer <= high
            ):
                raise ValueError
            clean[key] = integer
        except (ValueError, TypeError, OverflowError):
            errors[key] = error
    return clean, errors


class RoEtollConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure accounts in the ro_etoll domain."""

    VERSION = 1

    async def _test_credentials(self, username: str, password: str) -> dict[str, str]:
        try:
            api = RoEtollAPI(async_get_clientsession(self.hass), username, password)
            await api.authenticate()
            await api.get_profile()
            # Verify the endpoint required by the initial coordinator refresh too.
            await api.get_vehicles()
        except RoEtollAuthUnsupported:
            return {"base": "auth_unsupported"}
        except RoEtollAuthError:
            return {"base": "authentication_failed"}
        except RoEtollProfileError:
            return {"base": "profile_required"}
        except RoEtollConnectionError:
            return {"base": "cannot_connect"}
        except RoEtollApiError:
            return {"base": "invalid_response"}
        return {}

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            options, errors = validate_options(user_input)
            if not username:
                errors[CONF_USERNAME] = "authentication_failed"
            if not errors:
                await self.async_set_unique_id(username.casefold())
                self._abort_if_unique_id_configured()
                errors = await self._test_credentials(
                    username, user_input[CONF_PASSWORD]
                )
            if not errors:
                return self.async_create_entry(
                    title=f"ro_etoll ({username})",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                    options=options,
                )
        schema = {
            vol.Required(CONF_USERNAME): USERNAME,
            vol.Required(CONF_PASSWORD): PASSWORD,
            **options_schema(user_input or {}),
        }
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(schema), errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        return await self._credentials_step("reauth_confirm", user_input)

    async def async_step_reconfigure(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        return await self._credentials_step("reconfigure", user_input)

    async def _credentials_step(
        self, step: str, user_input: dict | None
    ) -> ConfigFlowResult:
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is None:
            return self.async_abort(reason="entry_missing")
        errors = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            if not username:
                errors[CONF_USERNAME] = "authentication_failed"
            elif any(
                other.entry_id != entry.entry_id
                and str(other.data.get(CONF_USERNAME, "")).strip().casefold()
                == username.casefold()
                for other in self.hass.config_entries.async_entries(DOMAIN)
            ):
                return self.async_abort(reason="already_configured")
            else:
                errors = await self._test_credentials(
                    username, user_input[CONF_PASSWORD]
                )
            if not errors:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                    unique_id=username.casefold(),
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(
                    reason="reauth_successful"
                    if step == "reauth_confirm"
                    else "reconfigure_successful"
                )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME, default=entry.data[CONF_USERNAME]
                ): USERNAME,
                vol.Required(CONF_PASSWORD): PASSWORD,
            }
        )
        return self.async_show_form(step_id=step, data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> config_entries.OptionsFlow:
        return RoEtollOptionsFlow()


class RoEtollOptionsFlow(config_entries.OptionsFlow):
    """Polling settings only."""

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            options, errors = validate_options(user_input)
            if not errors:
                return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=vol.Schema(options_schema(self.config_entry.options)),
        )
