"""The coordinator must keep the stored cookie in step with the live session."""
import asyncio
from types import SimpleNamespace

import pytest

from custom_components.tenup.api import TenupAuthError, TenupBookingError, TenupConnectionError
from custom_components.tenup.const import CONF_COOKIE
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
