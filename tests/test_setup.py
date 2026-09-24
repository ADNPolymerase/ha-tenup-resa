"""Setting up an entry must never leak its aiohttp session, and must eventually
ask for a new cookie instead of retrying for ever.

Both are regressions seen in production on 2026-09-24: an expired Ten'Up cookie
left the entry in setup_retry for some forty hours, writing "Unclosed client
session" to the log about every ten minutes, and never offering to re-authenticate.
"""
import asyncio
from types import SimpleNamespace

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components import tenup
from custom_components.tenup.api import (
    TenupAuthError,
    TenupConnectionError,
    new_session,
)
from custom_components.tenup.const import (
    AUTH_FAILURES,
    CONF_CLUB_CODE,
    CONF_COOKIE,
    DOMAIN,
)
from custom_components.tenup.coordinator import auth_state

COOKIE = "SHARED_SESSION_DRUPAL=aae6fe4e-0700-49d0-84ea-7b283f14affa"


def make_entry():
    return SimpleNamespace(
        entry_id="01ABCDEF",
        data={CONF_COOKIE: COOKIE, CONF_CLUB_CODE: "87654321"},
        options={},
        runtime_data=None,
        add_update_listener=lambda fn: (lambda: None),
        async_on_unload=lambda fn: None,
    )


def run_setup(first_refresh_error=None, forward_error=None):
    """Run async_setup_entry against fakes; return (outcome, was the session closed).

    The session is read before the test closes whatever is left, otherwise the
    cleanup would answer the very question being asked.
    """
    sessions = []

    class FakeCoordinator:
        def __init__(self, hass, entry, client):
            self.client = client

        async def async_config_entry_first_refresh(self):
            if first_refresh_error is not None:
                raise first_refresh_error

    async def forward(entry, platforms):
        if forward_error is not None:
            raise forward_error

    async def go():
        def session_factory():
            session = new_session()
            sessions.append(session)
            return session

        hass = SimpleNamespace(
            data={},
            config_entries=SimpleNamespace(async_forward_entry_setups=forward),
        )
        entry = make_entry()
        original_session, original_coordinator = tenup.new_session, tenup.TenupCoordinator
        tenup.new_session, tenup.TenupCoordinator = session_factory, FakeCoordinator
        try:
            outcome = await tenup.async_setup_entry(hass, entry)
        except BaseException as err:  # noqa: BLE001 - the outcome under test
            outcome = err
        finally:
            tenup.new_session, tenup.TenupCoordinator = original_session, original_coordinator
        closed = sessions[0].closed
        for session in sessions:
            await session.close()
        return outcome, closed

    return asyncio.run(go())


def test_a_successful_setup_keeps_its_session_open():
    """The session is the client's: it is closed on unload, not on setup."""
    outcome, closed = run_setup()
    assert outcome is True
    assert not closed


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (ConfigEntryNotReady("Ten'Up is down"), ConfigEntryNotReady),
        (ConfigEntryAuthFailed("cookie expired"), ConfigEntryAuthFailed),
        (TenupConnectionError("no answer"), ConfigEntryNotReady),
        (TenupAuthError("signed out"), ConfigEntryAuthFailed),
        (RuntimeError("something else entirely"), RuntimeError),
    ],
)
def test_a_failed_first_refresh_closes_the_session(raised, expected):
    """A retry every ten minutes would otherwise leak one session per attempt.

    ConfigEntryNotReady and ConfigEntryAuthFailed matter most: the coordinator
    turns our own errors into those, so they are what setup really raises.
    """
    outcome, closed = run_setup(first_refresh_error=raised)
    assert isinstance(outcome, expected), outcome
    assert closed, "the aiohttp session was left open"


def test_a_failed_platform_setup_closes_the_session_too():
    outcome, closed = run_setup(forward_error=ConfigEntryNotReady("calendar"))
    assert isinstance(outcome, ConfigEntryNotReady)
    assert closed


def test_a_cancelled_setup_closes_the_session():
    """Shutting Home Assistant down mid-setup must not leak either."""
    outcome, closed = run_setup(first_refresh_error=asyncio.CancelledError())
    assert isinstance(outcome, asyncio.CancelledError)
    assert closed


# --------------------------------------------------------- the failure counter
def test_the_counter_is_shared_by_every_coordinator_of_one_entry():
    """Setup retries throw the coordinator away: the count must not go with it."""
    hass = SimpleNamespace(data={})
    entry = make_entry()
    first = auth_state(hass, entry)
    first[AUTH_FAILURES] = 1
    assert auth_state(hass, entry) is first
    assert auth_state(hass, entry)[AUTH_FAILURES] == 1


def test_two_entries_count_separately():
    hass = SimpleNamespace(data={})
    one, other = make_entry(), make_entry()
    other.entry_id = "02ZZZZZZ"
    auth_state(hass, one)[AUTH_FAILURES] = 2
    assert auth_state(hass, other) == {}


def test_removing_an_entry_forgets_its_count():
    hass = SimpleNamespace(data={})
    entry = make_entry()
    auth_state(hass, entry)[AUTH_FAILURES] = 2
    asyncio.run(tenup.async_remove_entry(hass, entry))
    assert entry.entry_id not in hass.data[DOMAIN]
