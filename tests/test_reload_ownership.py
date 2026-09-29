"""Who reloads the entry after a reauth or a reconfigure.

Home Assistant refuses to have both: an update listener and a config flow that
schedules its own reload race each other, and the combination raises from Home
Assistant 2026.12 (core PR #169198). This integration keeps the listener, which
it needs to take a new friend without refetching the whole horizon, so the flow
must use the non-reloading variant and the listener must cover reauth itself.
"""
import asyncio
from pathlib import Path
from types import SimpleNamespace

from custom_components import tenup
from custom_components.tenup.const import CONF_COOKIE, CONF_FRIENDS
from custom_components.tenup.coordinator import TenupCoordinator

FLOW = (Path(tenup.__file__).parent / "config_flow.py").read_text(encoding="utf-8")
LIVE = "SHARED_SESSION_DRUPAL=aae6fe4e-0700-49d0-84ea-7b283f14affa"


def make(options, signature, stored=LIVE, live=LIVE):
    """A bare coordinator: only what absorb_update reads."""
    coordinator = TenupCoordinator.__new__(TenupCoordinator)
    coordinator.client = SimpleNamespace(session_cookie=live)
    coordinator.friends = []
    coordinator._options_signature = signature
    entry = SimpleNamespace(
        data={CONF_COOKIE: stored, "club_code": "87654321"}, options=options
    )
    return coordinator, entry


# ------------------------------------------------------------ the config flow
def test_the_flow_never_schedules_its_own_reload():
    assert "async_update_reload_and_abort" not in FLOW
    assert FLOW.count("async_update_and_abort") == 2, "reauth and reconfigure"


# ------------------------------------------------------------- absorb_update
def test_a_new_friend_is_taken_without_a_reload():
    coordinator, entry = make({CONF_FRIENDS: ["DOE"], "days_ahead": 7}, {"days_ahead": 7})
    assert coordinator.absorb_update(entry) is True
    assert coordinator.friends == ["DOE"]


def test_a_cookie_we_rotated_ourselves_is_taken_without_a_reload():
    """The coordinator writes back what its own jar already holds."""
    rotated = "SHARED_SESSION_DRUPAL=b0b0b0b0-0000-4000-8000-000000000000"
    coordinator, entry = make({}, {}, stored=rotated, live=rotated)
    assert coordinator.absorb_update(entry) is True


def test_another_option_asks_for_a_reload():
    coordinator, entry = make({"days_ahead": 3}, {"days_ahead": 7})
    assert coordinator.absorb_update(entry) is False


def test_a_cookie_we_did_not_write_asks_for_a_reload():
    """The regression: a reauth stores a cookie the client is not using yet.

    Home Assistant no longer reloads on our behalf, so absorbing this silently
    would leave the integration on the dead cookie until the next restart.
    """
    coordinator, entry = make({}, {}, stored="SHARED_SESSION_DRUPAL=fresh-from-reauth")
    assert coordinator.absorb_update(entry) is False
    assert coordinator.friends == [], "nothing is taken from a change we refuse"


# ------------------------------------------------------- the listener itself
def run_listener(absorbed):
    reloads = []

    async def async_reload(entry_id):
        reloads.append(entry_id)

    hass = SimpleNamespace(config_entries=SimpleNamespace(async_reload=async_reload))
    entry = SimpleNamespace(
        entry_id="01ABCDEF",
        runtime_data=SimpleNamespace(absorb_update=lambda _entry: absorbed),
    )

    async def go():
        await tenup._async_update_listener(hass, entry)

    asyncio.run(go())
    return reloads


def test_the_listener_reloads_what_it_cannot_absorb():
    assert run_listener(False) == ["01ABCDEF"]


def test_the_listener_stays_quiet_on_an_absorbed_change():
    assert run_listener(True) == []
