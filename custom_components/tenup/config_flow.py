"""Config flow for Ten'Up."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
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
    WrongCookieError,
    TenupAuthError,
    TenupClient,
    TenupConnectionError,
    cookie_candidates,
    new_session,
    parse_cookie_header,
)
from .const import (
    AUTH_FAILURES,
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
from .coordinator import auth_state

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
            # Straight to this entry's own club grid: the shared cookie only
            # exists inside the reservation area, not on the Ten'Up home page.
            # Without a club code there is no grid to aim at, so stay on the site
            # rather than build a /club/None/ address.
            "club_url": (
                f"https://tenup.fft.fr/club/{self._club_code}/reservations/"
                f"{dt_util.now():%Y%m%d}"
                if self._club_code
                else "https://tenup.fft.fr"
            ),
        }

    def _accept_new_session(self, entry: ConfigEntry) -> None:
        """Hand a freshly pasted session a clean slate, then wake the entry.

        The refusal count is what makes the integration ask for a new cookie
        only once Ten'Up has said no twice in a row, and it deliberately
        outlives the coordinator. It must not outlive the cookie it was counted
        against: a session just validated by this flow starts at zero, or a
        single hiccup on the first refresh would send the user straight back
        here, which is exactly what counting to two is meant to avoid.
        """
        auth_state(self.hass, entry).pop(AUTH_FAILURES, None)
        self._schedule_reload_if_dormant(entry)

    def _schedule_reload_if_dormant(self, entry: ConfigEntry) -> None:
        """Wake an entry that failed to set up, once it has a working session.

        The update listener owns every reload, but it is registered at the end
        of a successful setup: an entry that never got that far has none, and a
        freshly pasted session would sit there doing nothing until the next
        restart of Home Assistant. That is exactly the entry a user is most
        likely to be reauthenticating.
        """
        if entry.state is not ConfigEntryState.LOADED:
            self.hass.config_entries.async_schedule_reload(entry.entry_id)

    async def _async_validate_cookie(self, cookie: str, club_code: str) -> tuple[str | None, str]:
        """Try what the user pasted; returns (error, cookie to store)."""
        try:
            candidates = cookie_candidates(cookie)
            for candidate in candidates:
                parse_cookie_header(candidate)
        except WrongCookieError:
            # Both cookies sit one above the other and both hold a UUID: saying
            # which one was taken beats letting it fail as an expired session.
            return "wrong_cookie", cookie
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
                # Not the reloading variant: a loaded entry has an update
                # listener, and letting Home Assistant reload too would race
                # with it. Combining both raises an error from HA 2026.12.
                self._accept_new_session(entry)
                return self.async_update_and_abort(
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
                # See the reconfigure step: the update listener owns the reload.
                self._accept_new_session(entry)
                return self.async_update_and_abort(entry, data_updates={CONF_COOKIE: cookie})
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
