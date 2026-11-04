"""Data update coordinator for Ten'Up."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    TenupAuthError,
    TenupBookingError,
    TenupClient,
    TenupConnectionError,
    TenupPartnerRequired,
)
from .const import (
    AUTH_FAILURES,
    MAX_PLAYER_LOOKUPS,
    CONF_COOKIE,
    CONF_DAYS_AHEAD,
    CONF_FRIENDS,
    CONF_SCAN_INTERVAL,
    DEFAULT_DAYS_AHEAD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SLOT_FREE,
    SLOT_MINE,
)
from .models import (
    Partner,
    Planning,
    Slot,
    parse_partner_choice,
    partner_search_term,
    resolve_partner,
)

_LOGGER = logging.getLogger(__name__)


def auth_state(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, int]:
    """Per-entry counters that must outlive the coordinator holding them.

    A setup that fails is retried with a brand new coordinator, so anything kept
    on the coordinator itself restarts at zero every few minutes.
    """
    return hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})


@dataclass(slots=True)
class TenupData:
    """Everything the entities need."""

    plannings: dict[date, Planning] = field(default_factory=dict)
    fetched_at: datetime | None = None

    @property
    def courts(self) -> list:
        for planning in self.plannings.values():
            if planning.courts:
                return planning.courts
        return []

    @property
    def free_slots(self) -> list[Slot]:
        now = dt_util.now()
        return sorted(
            (s for p in self.plannings.values() for s in p.slots if s.state == SLOT_FREE and s.end > now),
            key=lambda s: (s.start, s.court_name),
        )

    @property
    def my_slots(self) -> list[Slot]:
        return sorted(
            (s for p in self.plannings.values() for s in p.slots if s.state == SLOT_MINE),
            key=lambda s: s.start,
        )

    def find_slot(self, court_id: str, start: datetime) -> Slot | None:
        planning = self.plannings.get(start.date())
        if planning is None:
            return None
        return planning.find(str(court_id), start)

    def find_reservation(self, reservation_id: str) -> Slot | None:
        for slot in self.my_slots:
            if slot.reservation_id == str(reservation_id):
                return slot
        return None


class TenupCoordinator(DataUpdateCoordinator[TenupData]):
    """Fetch the reservation grid for the coming days."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: TenupClient) -> None:
        minutes = entry.options.get(CONF_SCAN_INTERVAL)
        interval = timedelta(minutes=minutes) if minutes else DEFAULT_SCAN_INTERVAL
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data.get('club_code')}",
            update_interval=interval,
            config_entry=entry,
        )
        self.client = client
        self.entry = entry
        self._players_cache: dict[str, int] = {}
        self._store: Store = Store(hass, 1, f"{DOMAIN}_players_{entry.entry_id}")
        self._cache_loaded = False
        self.friends: list[str] = list(entry.options.get(CONF_FRIENDS) or [])
        self._options_signature = {k: v for k, v in entry.options.items() if k != CONF_FRIENDS}

    @property
    def _auth_failures(self) -> int:
        """How many times in a row Ten'Up has said the session is signed out.

        Read from hass.data rather than kept here: a failed setup builds a new
        coordinator on every retry, so a counter living on the coordinator would
        restart at zero and the second refusal, the one that asks for a new
        cookie, would never come.
        """
        return auth_state(self.hass, self.entry).get(AUTH_FAILURES, 0)

    @_auth_failures.setter
    def _auth_failures(self, value: int) -> None:
        auth_state(self.hass, self.entry)[AUTH_FAILURES] = value

    @property
    def days_ahead(self) -> int:
        return int(self.entry.options.get(CONF_DAYS_AHEAD, DEFAULT_DAYS_AHEAD))

    def absorb_update(self, entry: ConfigEntry) -> bool:
        """Take a change in place; False asks the caller for a reload.

        Two writes must not cost a full refetch of every day of the horizon: the
        card adding a friend, and the coordinator saving a cookie Ten'Up has
        rotated. Everything else needs a reload, and a cookie the coordinator did
        not write is exactly that: it comes from a reauth or a reconfigure, and
        only a reload puts it in the client.
        """
        options = dict(entry.options)
        friends = list(options.pop(CONF_FRIENDS, []) or [])
        if options != self._options_signature:
            return False
        if entry.data.get(CONF_COOKIE) != self.client.session_cookie:
            return False
        self.friends = friends
        return True

    async def _load_players_cache(self) -> None:
        """Read back what earlier refreshes learned about each slot.

        A key without a court comes from before the court was part of it. Those
        entries taught one court's answer to every court sharing its time band,
        which is how a one-player cell ended up on a court the club wants two
        players on, so they are dropped rather than migrated.
        """
        if self._cache_loaded:
            return
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self._players_cache.update(
                {str(k): int(v) for k, v in stored.items() if ":" in str(k)}
            )
        self._cache_loaded = True

    async def _async_update_data(self) -> TenupData:
        await self._load_players_cache()
        today = dt_util.now().date()
        data = TenupData()
        for offset in range(self.days_ahead):
            day = today + timedelta(days=offset)
            try:
                planning = await self.client.async_get_planning(day)
            except TenupAuthError as err:
                # One refusal is not proof: ask the user for a new cookie only
                # once Ten'Up has said it twice in a row. The count spans setup
                # retries, so an expired cookie reaches the second refusal
                # instead of retrying for ever.
                self._auth_failures += 1
                if self._auth_failures < 2:
                    raise UpdateFailed(f"{err} (retrying before asking to sign in again)") from err
                raise ConfigEntryAuthFailed(str(err)) from err
            except TenupConnectionError as err:
                if data.plannings:
                    _LOGGER.warning("Ten'Up: stopping at %s: %s", day, err)
                    break
                raise UpdateFailed(str(err)) from err
            self._auth_failures = 0
            data.plannings[day] = planning
            # Ten'Up states the last day it will take a booking for; asking for
            # the day after only returns an empty grid.
            if planning.window_end and day >= planning.window_end:
                break
        await self._annotate_required_players(data)
        self._persist_rotated_cookie()
        data.fetched_at = dt_util.now()
        return data

    def _persist_rotated_cookie(self) -> None:
        """Write back the session cookie when Ten'Up has replaced it.

        Only touches ``data``, never ``options``, so the update listener treats it
        as a no-op and the integration is not reloaded behind the user's back.
        """
        current = self.client.session_cookie
        if not current or current == self.entry.data.get(CONF_COOKIE):
            return
        _LOGGER.debug("Ten'Up handed out a new session cookie, saving it")
        self.hass.config_entries.async_update_entry(
            self.entry, data={**self.entry.data, CONF_COOKIE: current}
        )

    async def _annotate_required_players(self, data: TenupData) -> None:
        """Tag each free slot with how many players its config needs (Couvert = 2, ...).

        Keyed on idCreneau (court + time band), learned once per config and cached,
        so a club that varies the rule by hour is handled correctly. Bounded per refresh.
        """
        free = [
            s
            for planning in data.plannings.values()
            for s in planning.slots
            if s.state == SLOT_FREE and s.creneau_id
        ]
        pending: dict[str, Slot] = {}
        for slot in free:
            key = self._players_key(slot)
            if key not in self._players_cache and key not in pending:
                pending[key] = slot
        learned = 0
        for key, slot in list(pending.items())[:MAX_PLAYER_LOOKUPS]:
            players = await self.client.async_required_players(slot)
            if players is not None:
                self._players_cache[key] = players
                learned += 1
        if learned:
            await self._store.async_save(self._players_cache)
        for slot in free:
            slot.required_players = self._players_cache.get(self._players_key(slot))

    @staticmethod
    def _players_key(slot: Slot) -> str:
        """How one slot configuration is cached.

        Eligibility is asked for a court and a time band together, and the club
        answers for that pair: two courts sharing a band do not share the rule
        on how many players it wants. The court therefore belongs in the key.
        """
        return f"{slot.court_id}:{slot.creneau_id}"

    async def _remember_required_players(self, slot: Slot, required: int) -> None:
        """Take what a refused booking just taught us about a slot.

        The club has the last word, and it may change it. Writing the real
        number down here, on this slot and on every other cell of the same
        configuration, is what turns a refusal the user cannot act on into a
        cell that asks for a partner on the next click.
        """
        if not slot.creneau_id:
            return
        key = self._players_key(slot)
        if self._players_cache.get(key) == required:
            return
        self._players_cache[key] = required
        await self._store.async_save(self._players_cache)

        def patch() -> None:
            for planning in (self.data.plannings.values() if self.data else []):
                for other in planning.slots:
                    if other.state == SLOT_FREE and self._players_key(other) == key:
                        other.required_players = required

        self._apply_locally(patch)

    async def async_book(self, slot: Slot, partner: str | None = None) -> str:
        chosen = await self._resolve_partner(partner) if partner else None
        try:
            result = await self.client.async_book(slot, chosen)
        except TenupPartnerRequired as err:
            # Never let the bookkeeping hide the refusal it came from: the user
            # is owed Ten'Up's own message, not a storage error.
            try:
                await self._remember_required_players(slot, err.required)
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Could not record the player count", exc_info=True)
            raise
        self._apply_locally(slot.mark_mine)
        await self.async_request_refresh()
        return result

    async def _resolve_partner(self, partner: str) -> Partner:
        """Turn a stored friend into the club member Ten'Up expects.

        The card stores the member id alongside the name, so the usual case
        needs no call at all. A bare name, typed by hand or saved by an older
        version, is searched for instead; two homonyms are never resolved
        silently, since a father and his son share a surname.
        """
        known = parse_partner_choice(partner)
        if known is not None:
            return known
        results = await self.client.async_search_partner(partner_search_term(partner))
        candidates = resolve_partner(results, partner)
        if not candidates:
            raise TenupBookingError(
                f"Aucun adhérent du club ne correspond à « {partner} »"
            )
        if len(candidates) > 1:
            names = ", ".join(found.name for found in candidates)
            raise TenupBookingError(
                f"Plusieurs adhérents correspondent à « {partner} » : {names}. "
                "Précisez le prénom."
            )
        return candidates[0]

    async def async_cancel(self, slot: Slot) -> None:
        try:
            await self.client.async_cancel(slot)
        except (TenupBookingError, TenupConnectionError):
            # A cancellation may have gone through whatever the answer said:
            # reconcile the grid now instead of in up to fifteen minutes. An auth
            # error is left out on purpose: the refresh would only count it twice.
            await self.async_request_refresh()
            raise
        self._apply_locally(slot.mark_free)
        await self.async_request_refresh()

    def _apply_locally(self, change) -> None:
        """Reflect a change Ten'Up has already accepted, without waiting.

        async_request_refresh is debounced by about ten seconds and a full
        refresh fetches every day again, so the grid kept showing the old state
        long enough that the card had to be reloaded by hand. The call has
        succeeded, so the cell is updated now and the background refresh only
        reconciles afterwards.
        """
        change()
        if self.data is not None:
            self.async_set_updated_data(self.data)
