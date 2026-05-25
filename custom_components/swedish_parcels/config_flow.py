from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import (
    CONF_AIRMEE_PHONE_HASH,
    CONF_IMAP_HOST,
    CONF_IMAP_MAILBOX,
    CONF_IMAP_PASSWORD,
    CONF_IMAP_PORT,
    CONF_IMAP_USER,
    CONF_LOOKBACK_DAYS,
    CONF_PARCEL_SENDERS,
    CONF_SCAN_INTERVAL_MIN,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MAILBOX,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL_MIN,
    DEFAULT_SENDERS,
    DOMAIN,
)


class SwedishParcelsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_IMAP_USER])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Parcels ({user_input[CONF_IMAP_USER]})",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_IMAP_HOST, default="imap.gmail.com"): str,
                vol.Required(CONF_IMAP_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_IMAP_USER): str,
                vol.Required(CONF_IMAP_PASSWORD): str,
                vol.Optional(CONF_IMAP_MAILBOX, default=DEFAULT_MAILBOX): str,
                vol.Optional(CONF_PARCEL_SENDERS, default=DEFAULT_SENDERS): str,
                vol.Optional(CONF_AIRMEE_PHONE_HASH, default=""): str,
                vol.Optional(CONF_SCAN_INTERVAL_MIN, default=DEFAULT_SCAN_INTERVAL_MIN): int,
                vol.Optional(CONF_LOOKBACK_DAYS, default=DEFAULT_LOOKBACK_DAYS): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SwedishParcelsOptionsFlow(config_entry)


class SwedishParcelsOptionsFlow(OptionsFlow):
    def __init__(self, config_entry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_PARCEL_SENDERS,
                    default=current.get(CONF_PARCEL_SENDERS, DEFAULT_SENDERS),
                ): str,
                vol.Optional(
                    CONF_AIRMEE_PHONE_HASH,
                    default=current.get(CONF_AIRMEE_PHONE_HASH, ""),
                ): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL_MIN,
                    default=current.get(CONF_SCAN_INTERVAL_MIN, DEFAULT_SCAN_INTERVAL_MIN),
                ): int,
                vol.Optional(
                    CONF_LOOKBACK_DAYS,
                    default=current.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS),
                ): int,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
