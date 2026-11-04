"""The coordinator must keep the stored cookie in step with the live session."""
import asyncio
from types import SimpleNamespace

import pytest

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.tenup.api import TenupAuthError, TenupBookingError, TenupConnectionError
from custom_components.tenup.const import AUTH_FAILURES, CONF_COOKIE, DOMAIN
from custom_components.tenup.coordinator import TenupCoordinator

NAME = "SSESS7ba44afc36c80c3faa2b8fa87e7742c5"


def make(stored, live, options=None):
    """A bare coordinator: only what _persist_rotated_cookie touches."""
    coordinator = TenupCoordinator.__new__(TenupCoordinator)
    saved = []
    coordinator.client = SimpleNamespace(session_cookie=live)
    coordinator.entry = SimpleNamespace(
        data={CONF_COOKIE: stored, "club_code": "87654321"},
        options=options or {},
    )
    coordinator.hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_update_entry=lambda entry, **kw: saved.append(kw)
        )
    )
    return coordinator, saved


def test_a_rotated_cookie_is_written_back():
    coordinator, saved = make(f"{NAME}=old", f"{NAME}=rotated")
    coordinator._persist_rotated_cookie()
    assert saved == [{"data": {CONF_COOKIE: f"{NAME}=rotated", "club_code": "87654321"}}]


def test_an_unchanged_cookie_writes_nothing():
    """A write on every refresh would rewrite the config entry every 15 minutes."""
    coordinator, saved = make(f"{NAME}=same", f"{NAME}=same")
    coordinator._persist_rotated_cookie()
    assert saved == []


def test_an_empty_jar_never_overwrites_the_stored_cookie():
    """No session cookie in the jar is not a reason to forget the one that works."""
    coordinator, saved = make(f"{NAME}=works", None)
    coordinator._persist_rotated_cookie()
    assert saved == []


def test_the_club_code_survives_the_rewrite():
    coordinator, saved = make(f"{NAME}=old", f"{NAME}=new")
    coordinator._persist_rotated_cookie()
    assert saved[0]["data"]["club_code"] == "87654321"


def test_options_are_never_touched():
    """Writing options would make the update listener reload the integration."""
    coordinator, saved = make(f"{NAME}=old", f"{NAME}=new", options={"days_ahead": 7})
    coordinator._persist_rotated_cookie()
    assert "options" not in saved[0]


SHARED = "SHARED_SESSION_DRUPAL=aae6fe4e-0700-49d0-84ea-7b283f14affa"


def test_a_minted_session_never_replaces_the_shared_cookie():
    """The durable credential must survive every refresh, whatever Drupal mints."""
    coordinator, saved = make(SHARED, SHARED)
    coordinator._persist_rotated_cookie()
    assert saved == []


def test_upgrading_from_ssess_to_the_shared_cookie_is_saved():
    """A user who re-pastes the shared cookie stops depending on the 23 day session."""
    coordinator, saved = make(f"{NAME}=old", SHARED)
    coordinator._persist_rotated_cookie()
    assert saved[0]["data"][CONF_COOKIE] == SHARED


# ---------------------------------------------------------------- cancellation
def make_cancel(error=None):
    """A bare coordinator for async_cancel: a client that succeeds or raises."""
    coordinator = TenupCoordinator.__new__(TenupCoordinator)
    refreshes = []

    async def cancel(slot):
        if error is not None:
            raise error

    async def refresh():
        refreshes.append(True)

    coordinator.client = SimpleNamespace(async_cancel=cancel)
    coordinator.data = None
    coordinator.async_request_refresh = refresh
    slot = SimpleNamespace(freed=False)
    slot.mark_free = lambda: setattr(slot, "freed", True)
    return coordinator, slot, refreshes


def test_a_confirmed_cancellation_frees_the_cell_and_refreshes():
    coordinator, slot, refreshes = make_cancel()
    asyncio.run(coordinator.async_cancel(slot))
    assert slot.freed
    assert refreshes == [True]


@pytest.mark.parametrize("error", [TenupConnectionError("x"), TenupBookingError("x")])
def test_a_failed_cancellation_still_reconciles_the_grid(error):
    """It may have gone through anyway: do not leave the card wrong for 15 minutes."""
    coordinator, slot, refreshes = make_cancel(error)
    with pytest.raises(type(error)):
        asyncio.run(coordinator.async_cancel(slot))
    assert not slot.freed, "a cell is freed only on a confirmed cancellation"
    assert refreshes == [True]


def test_an_auth_error_does_not_trigger_a_refresh():
    """The refresh would hit the same dead cookie and count the failure twice."""
    coordinator, slot, refreshes = make_cancel(TenupAuthError("x"))
    with pytest.raises(TenupAuthError):
        asyncio.run(coordinator.async_cancel(slot))
    assert refreshes == []


# --------------------------------------------- asking for a new cookie, at last
def make_refresh(errors, hass_data=None):
    """A bare coordinator for _async_update_data: one fake day, scripted errors.

    ``hass_data`` is the real hass.data, shared on purpose so a test can hand it
    to a second coordinator the way a setup retry does.
    """
    coordinator = TenupCoordinator.__new__(TenupCoordinator)
    calls = []
    queue = list(errors)

    async def async_get_planning(day):
        calls.append(day)
        error = queue.pop(0) if queue else None
        if error is not None:
            raise error
        return SimpleNamespace(slots=[], courts=[], window_end=None)

    coordinator.client = SimpleNamespace(
        async_get_planning=async_get_planning, session_cookie=f"{NAME}=live"
    )
    coordinator.entry = SimpleNamespace(
        data={CONF_COOKIE: f"{NAME}=live", "club_code": "87654321"},
        options={"days_ahead": 1},
        entry_id="01ABCDEF",
    )
    coordinator.hass = SimpleNamespace(data={} if hass_data is None else hass_data)
    coordinator._cache_loaded = True
    coordinator._players_cache = {}
    return coordinator, calls


def test_one_refusal_only_fails_the_refresh():
    """A single odd answer is not proof: do not send the user hunting a cookie."""
    coordinator, _calls = make_refresh([TenupAuthError("signed out")])
    with pytest.raises(UpdateFailed):
        asyncio.run(coordinator._async_update_data())


def test_a_second_refusal_asks_for_a_new_cookie():
    data = {}
    first, _ = make_refresh([TenupAuthError("signed out")], data)
    with pytest.raises(UpdateFailed):
        asyncio.run(first._async_update_data())
    second, _ = make_refresh([TenupAuthError("signed out")], data)
    with pytest.raises(ConfigEntryAuthFailed):
        asyncio.run(second._async_update_data())


def test_the_count_survives_the_coordinator_a_setup_retry_throws_away():
    """The regression: an expired cookie retried for forty hours without ever
    offering to re-authenticate, because each retry started counting again."""
    data = {}
    for _ in range(5):
        coordinator, _ = make_refresh([TenupAuthError("signed out")], data)
        try:
            asyncio.run(coordinator._async_update_data())
        except (UpdateFailed, ConfigEntryAuthFailed):
            pass
    assert data[DOMAIN]["01ABCDEF"][AUTH_FAILURES] >= 2


def test_a_successful_day_clears_the_count():
    """A cookie that works again must not be one refusal away from a reauth."""
    data = {DOMAIN: {"01ABCDEF": {AUTH_FAILURES: 1}}}
    coordinator, _ = make_refresh([None], data)
    asyncio.run(coordinator._async_update_data())
    assert data[DOMAIN]["01ABCDEF"][AUTH_FAILURES] == 0


def test_a_connection_error_never_counts_as_a_refusal():
    """A Queue-it waiting room or a bot challenge is not an expired cookie."""
    data = {}
    for _ in range(5):
        coordinator, _ = make_refresh([TenupConnectionError("queue-it")], data)
        with pytest.raises(UpdateFailed):
            asyncio.run(coordinator._async_update_data())
    assert data.get(DOMAIN, {}).get("01ABCDEF", {}).get(AUTH_FAILURES, 0) == 0


# ------------------------------------------- how many players a slot asks for
from datetime import date, datetime, timedelta  # noqa: E402

from custom_components.tenup.api import TenupPartnerRequired  # noqa: E402
from custom_components.tenup.const import SLOT_FREE  # noqa: E402
from custom_components.tenup.coordinator import TenupData  # noqa: E402
from custom_components.tenup.models import Planning, Slot  # noqa: E402

DAY = date(2026, 11, 4)


def free_slot(court_id, creneau_id, hour=8):
    start = datetime(2026, 11, 4, hour)
    return Slot(
        court_id=court_id,
        court_name=f"COURT {court_id}",
        start=start,
        end=start + timedelta(hours=1),
        state=SLOT_FREE,
        creneau_id=creneau_id,
    )


def make_players(slots, answers, stored=None):
    """A bare coordinator for the required-players cache and its store."""
    coordinator = TenupCoordinator.__new__(TenupCoordinator)
    asked = []
    saves = []

    async def async_required_players(slot):
        asked.append((slot.court_id, slot.creneau_id))
        return answers.get((slot.court_id, slot.creneau_id))

    async def async_load():
        return stored

    async def async_save(payload):
        saves.append(dict(payload))

    coordinator.client = SimpleNamespace(
        async_required_players=async_required_players,
        session_cookie=f"{NAME}=live",
    )
    coordinator._store = SimpleNamespace(async_load=async_load, async_save=async_save)
    coordinator._players_cache = {}
    coordinator._cache_loaded = stored is None
    coordinator.data = TenupData(plannings={DAY: Planning(day=DAY, slots=list(slots))})
    coordinator.async_set_updated_data = lambda data: None
    return coordinator, asked, saves


def test_two_courts_sharing_a_time_band_are_asked_separately():
    """The regression: one court's answer was taught to every court of the band.

    Ten'Up answers eligibility for a court and a band together, so a covered
    court wanting two players and an outdoor one wanting a single player can
    carry the very same band id.
    """
    slots = [free_slot("37195", "900"), free_slot("21101", "900")]
    coordinator, asked, _ = make_players(
        slots, {("37195", "900"): 2, ("21101", "900"): 1}
    )
    asyncio.run(coordinator._annotate_required_players(coordinator.data))
    assert sorted(asked) == [("21101", "900"), ("37195", "900")]
    assert [s.required_players for s in slots] == [2, 1]


def test_every_cell_of_one_court_and_band_is_learned_once():
    slots = [free_slot("37195", "900", hour=h) for h in (8, 9, 10)]
    coordinator, asked, _ = make_players(slots, {("37195", "900"): 2})
    asyncio.run(coordinator._annotate_required_players(coordinator.data))
    assert asked == [("37195", "900")], "one lookup per court and band, not per cell"
    assert [s.required_players for s in slots] == [2, 2, 2]


def test_a_cache_written_before_the_court_was_part_of_the_key_is_dropped():
    """Those entries hold a band id alone, and are what put a one-player cell on
    a court the club wants two players on."""
    coordinator, _asked, _ = make_players([], {}, stored={"900": 1, "37195:900": 2})
    asyncio.run(coordinator._load_players_cache())
    assert coordinator._players_cache == {"37195:900": 2}


def test_a_refused_booking_records_what_the_club_asked_for():
    slots = [free_slot("37195", "900", hour=h) for h in (8, 9)]
    coordinator, _asked, saves = make_players(slots, {})
    coordinator._players_cache["37195:900"] = 1

    async def book(slot, partner):
        raise TenupPartnerRequired(2)

    refreshes = []

    async def refresh():
        refreshes.append(True)

    coordinator.client.async_book = book
    coordinator.async_request_refresh = refresh

    with pytest.raises(TenupPartnerRequired):
        asyncio.run(coordinator.async_book(slots[0]))

    assert coordinator._players_cache["37195:900"] == 2
    assert saves == [{"37195:900": 2}], "the truth must survive a restart"
    assert [s.required_players for s in slots] == [2, 2], "every cell of the band"
    assert refreshes == [], "a refused booking books nothing to reconcile"


def test_recording_the_same_number_twice_writes_nothing():
    coordinator, _asked, saves = make_players([], {})
    coordinator._players_cache["37195:900"] = 2
    asyncio.run(coordinator._remember_required_players(free_slot("37195", "900"), 2))
    assert saves == []
