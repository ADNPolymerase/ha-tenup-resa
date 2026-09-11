"""Config flow for Ten'Up."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import dt as dt_util

from .api import (
    TenupAuthError,
    TenupClient,
    TenupConnectionError,
    cookie_candidates,
    new_session,
    parse_cookie_header,
)
from .const import (
    CONF_CLUB_CODE,
    CONF_CLUB_NAME,
    CONF_COOKIE,
    CONF_DAYS_AHEAD,
    CONF_FRIENDS,
    CONF_SCAN_INTERVAL,
    DEFAULT_DAYS_AHEAD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

CONF_QUERY = "query"
CONF_CLUB = "club"

STEP_CLUB_SCHEMA = vol.Schema({vol.Required(CONF_QUERY): str})
STEP_COOKIE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COOKIE): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD, multiline=False)
        )
    }
)


class TenupConfigFlow(ConfigFlow, domain=DOMAIN):
    """Search the club with the public API, then ask for the session cookie."""

    VERSION = 1

    def __init__(self) -> None:
        self._clubs: dict[str, str] = {}
        self._club_code: str | None = None
        self._club_name: str | None = None

    # ----------------------------------------------------------------- club
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            query = user_input[CONF_QUERY].strip()
            if query.isdigit() and len(query) >= 7:
                self._club_code = query
                self._club_name = f"Club {query}"
                return await self.async_step_cookie()
            try:
                clubs = await TenupClient.async_search_clubs(async_get_clientsession(self.hass), query)
            except TenupConnectionError:
                errors["base"] = "cannot_connect"
            else:
                if not clubs:
                    errors["base"] = "no_club"
                else:
                    self._clubs = {str(c["code"]): f"{c['nom']} ({c.get('comite', '')})" for c in clubs}
                    return await self.async_step_club()
        return self.async_show_form(step_id="user", data_schema=STEP_CLUB_SCHEMA, errors=errors)

    async def async_step_club(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._club_code = user_input[CONF_CLUB]
            self._club_name = self._clubs.get(self._club_code, self._club_code).split(" (")[0]
            return await self.async_step_cookie()
        schema = vol.Schema(
            {
                vol.Required(CONF_CLUB): SelectSelector(
                    SelectSelectorConfig(
                        options=[SelectOptionDict(value=code, label=name) for code, name in self._clubs.items()],
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="club", data_schema=schema)

    # --------------------------------------------------------------- cookie
    async def async_step_cookie(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            assert self._club_code is not None
            error, cookie = await self._async_validate_cookie(user_input[CONF_COOKIE], self._club_code)
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(self._club_code)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Ten'Up {self._club_name}",
                    data={
                        CONF_CLUB_CODE: self._club_code,
                        CONF_CLUB_NAME: self._club_name,
                        CONF_COOKIE: cookie,
                    },
                )
        return self.async_show_form(
            step_id="cookie",
            data_schema=STEP_COOKIE_SCHEMA,
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    def _placeholders(self) -> dict[str, str]:
        return {
            "club": self._club_name or "",
            "club_code": self._club_code or "",
            "site": "tenup.fft.fr",
            "site_url": "https://tenup.fft.fr",
        }

    async def _async_validate_cookie(self, cookie: str, club_code: str) -> tuple[str | None, str]:
        """Try what the user pasted; returns (error, cookie to store)."""
        try:
            candidates = cookie_candidates(cookie)
            for candidate in candidates:
                parse_cookie_header(candidate)
        except ValueError:
            return "invalid_cookie", cookie
        error = "invalid_auth"
        session = new_session()
        try:
            for candidate in candidates:
                client = TenupClient(session, candidate, club_code, dt_util.get_default_time_zone())
                try:
                    planning = await client.async_validate()
                except TenupAuthError:
                    error = "invalid_auth"
                    continue
                except TenupConnectionError:
                    return "cannot_connect", candidate
                if not planning.courts:
                    return "no_planning", candidate
                return None, candidate
        finally:
            await session.close()
        return error, cookie

    # ---------------------------------------------------------- reconfigure
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user hand over a new session without waiting for the old one to die.

        Needed to move an existing setup to the longer lived shared cookie, and to
        recover from a session revoked on the Ten'Up side (which looks fine to us
        until the next refresh).
        """
        entry = self._get_reconfigure_entry()
        self._club_code = entry.data[CONF_CLUB_CODE]
        self._club_name = entry.data.get(CONF_CLUB_NAME)
        errors: dict[str, str] = {}
        if user_input is not None:
            error, cookie = await self._async_validate_cookie(
                user_input[CONF_COOKIE], self._club_code
            )
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_COOKIE: cookie}
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_COOKIE_SCHEMA,
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    # --------------------------------------------------------------- reauth
    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        self._club_code = entry_data[CONF_CLUB_CODE]
        self._club_name = entry_data.get(CONF_CLUB_NAME)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            assert self._club_code is not None
            error, cookie = await self._async_validate_cookie(user_input[CONF_COOKIE], self._club_code)
            if error:
                errors["base"] = error
            else:
                entry = self._get_reauth_entry()
                return self.async_update_reload_and_abort(entry, data_updates={CONF_COOKIE: cookie})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_COOKIE_SCHEMA,
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return TenupOptionsFlow()


class TenupOptionsFlow(OptionsFlow):
    """Horizon and refresh interval."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DAYS_AHEAD, default=options.get(CONF_DAYS_AHEAD, DEFAULT_DAYS_AHEAD)
                ): NumberSelector(NumberSelectorConfig(min=1, max=14, step=1, mode=NumberSelectorMode.BOX)),
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds() // 60)),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL_MINUTES, max=240, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="min"
                    )
                ),
                vol.Optional(
                    CONF_FRIENDS, default=list(options.get(CONF_FRIENDS) or [])
                ): TextSelector(TextSelectorConfig(multiple=True)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
