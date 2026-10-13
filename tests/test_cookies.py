"""What the user is allowed to paste as a session, and what is turned away.

Two Ten'Up cookies sit one above the other in the browser's cookie view, both
holding a UUID, and only one of them signs anyone in. Nothing in a value says
which is which, so the refusal has to.
"""

import pytest

from custom_components.tenup.api import (
    SESSION_COOKIE_NAME,
    WrongCookieError,
    cookie_candidates,
    parse_cookie_header,
)

UUID = "f1e2d3c4-0000-4a5b-8c9d-0e1f2a3b4c5d"
SESSION = f"{SESSION_COOKIE_NAME}={UUID}"


def test_the_value_alone_is_enough():
    """It is what double-clicking the Value cell puts on the clipboard."""
    assert cookie_candidates(UUID) == [SESSION]
    assert cookie_candidates(f"  {UUID} \n") == [SESSION]


def test_the_whole_pair_is_taken_too():
    assert cookie_candidates(SESSION) == [SESSION]
    assert cookie_candidates(f"Cookie: {SESSION}") == [SESSION]


def test_the_session_is_found_among_other_cookies():
    """Copying the row sometimes drags its neighbours along."""
    assert cookie_candidates(f"datadome=abc; {SESSION}; userStore=%7B%7D") == [SESSION]


def test_the_cookie_that_was_replaced_is_named_rather_than_tried():
    """The trap: it is one row away and holds a UUID that looks the same.

    Accepting it would turn a copying mistake into an expired session two
    screens later, which is exactly how an evening gets lost.
    """
    with pytest.raises(WrongCookieError):
        cookie_candidates(f"SHARED_SESSION_DRUPAL={UUID}")
    with pytest.raises(WrongCookieError):
        cookie_candidates("SSESS7ba44afc36c80c3faa2b8fa87e7742c5=Kj3-nV_9xQp2")
    with pytest.raises(WrongCookieError):
        cookie_candidates(f"datadome=x; SHARED_SESSION_DRUPAL={UUID}; _ga=1")


def test_the_session_wins_when_both_are_pasted():
    both = f"SHARED_SESSION_DRUPAL=aae6fe4e-0700-49d0-84ea-7b283f14affa; {SESSION}"
    assert cookie_candidates(both) == [SESSION]


@pytest.mark.parametrize(
    "pasted",
    [
        "",
        "   ",
        "bonjour",
        "abc-DEF_123",
        "curl 'https://tenup.fft.fr/api/back/v1/profil' -H 'accept: application/json'",
        "userStore=%7B%22isLogged%22%3Atrue%7D",
    ],
)
def test_anything_else_is_refused_now_rather_than_later(pasted):
    """Guessing would only move the refusal to the next screen."""
    with pytest.raises(ValueError):
        cookie_candidates(pasted)


def test_a_wrong_cookie_is_still_a_value_error():
    """The flow catches the precise one first, but nothing else has to know."""
    assert issubclass(WrongCookieError, ValueError)


def test_the_header_parser_reads_a_pair_and_a_whole_header():
    assert parse_cookie_header(SESSION) == {SESSION_COOKIE_NAME: UUID}
    assert parse_cookie_header(f"Cookie: {SESSION}; datadome=xyz") == {
        SESSION_COOKIE_NAME: UUID,
        "datadome": "xyz",
    }
    with pytest.raises(ValueError):
        parse_cookie_header("   ")


def test_the_flow_tells_the_two_cookies_apart():
    """A copying mistake earns its own message, not "session expired"."""
    import json
    from pathlib import Path

    from custom_components import tenup

    flow = (Path(tenup.__file__).parent / "config_flow.py").read_text(encoding="utf-8")
    assert "except WrongCookieError:" in flow
    assert '"wrong_cookie"' in flow

    texts = json.loads(
        (Path(tenup.__file__).parent / "translations/fr.json").read_text(encoding="utf-8")
    )
    message = texts["config"]["error"]["wrong_cookie"]
    assert "SHARED_SESSION_JAVA" in message and "SHARED_SESSION_DRUPAL" in message


def test_friend_list_is_cleaned_before_being_stored():
    """Short entries are the trap: Ten'Up labels club lessons with first names."""
    from custom_components.tenup.websocket import MAX_FRIENDS, clean_friends

    assert clean_friends(["  BLACKWELL  ", "Dyer"]) == ["BLACKWELL", "Dyer"]
    assert clean_friends(["Van   Dyke"]) == ["Van Dyke"], "inner spaces collapse"
    assert clean_friends(["Hale", "HALE", "hale"]) == ["Hale"], "case-insensitive de-dup"
    assert clean_friends(["", "  ", "a", "ab"]) == [], "nothing usable survives"
    assert clean_friends(["abc"]) == ["abc"], "three characters is the floor"
    assert len(clean_friends([f"ami{n}" for n in range(MAX_FRIENDS + 20)])) == MAX_FRIENDS
