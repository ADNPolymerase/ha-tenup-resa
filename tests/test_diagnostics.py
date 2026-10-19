"""Diagnostics are pasted into public issues, so two things must never be in them.

The session cookie, which signs its holder in, and the friends list: it holds
the names of other club members, and for a partner remembered from the card,
their Ten'Up member id. Every name and id below is invented.
"""
import asyncio
from datetime import date, datetime, timezone
from types import SimpleNamespace

from custom_components.tenup.const import CONF_COOKIE, CONF_FRIENDS
from custom_components.tenup.diagnostics import async_get_config_entry_diagnostics

COOKIE = "SHARED_SESSION_JAVA=f1e2d3c4-0000-4a5b-8c9d-0e1f2a3b4c5d"
FRIENDS = ["Partner One", "Partner Two (10000000002)"]


def diagnostics():
    planning = SimpleNamespace(
        slots=[1, 2, 3], free_slots=[1], my_slots=[2], window_end=date(2026, 10, 26)
    )
    entry = SimpleNamespace(
        data={CONF_COOKIE: COOKIE, "club_code": "11111111", "club_name": "Club"},
        options={CONF_FRIENDS: FRIENDS, "days_ahead": 7},
        runtime_data=SimpleNamespace(
            data=SimpleNamespace(
                fetched_at=datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc),
                courts=[SimpleNamespace(id=1, name="COURT 1")],
                plannings={date(2026, 10, 19): planning},
            )
        ),
    )
    return asyncio.run(async_get_config_entry_diagnostics(None, entry))


def test_the_friends_list_never_leaves_the_house():
    out = diagnostics()
    assert out["options"][CONF_FRIENDS] == "**REDACTED**"
    assert "Partner One" not in str(out)
    assert "10000000002" not in str(out)


def test_the_session_cookie_never_leaves_the_house():
    out = diagnostics()
    assert out["entry"][CONF_COOKIE] == "**REDACTED**"
    assert COOKIE not in str(out)


def test_what_is_useful_is_still_there():
    """Redacting must not empty the report: the rest is what gets diagnosed."""
    out = diagnostics()
    assert out["entry"]["club_code"] == "11111111"
    assert out["options"]["days_ahead"] == 7
    assert out["courts"] == [{"id": 1, "name": "COURT 1"}]
    assert out["days"]["2026-10-19"] == {
        "free": 1,
        "mine": 1,
        "total": 3,
        "window_end": "2026-10-26",
    }
