"""What the user pastes as a session, and what the card stores as friends.

Both outlive the site itself: Ten'Up rebuilt its member area in 2026 and kept
the very same cookie, so these are the parts of the integration a redesign has
no say over.
"""

import pytest

from custom_components.tenup.api import parse_cookie_header


def test_cookie_header():
    assert parse_cookie_header("SESSabc=123") == {"SESSabc": "123"}
    assert parse_cookie_header("Cookie: SESSabc=123; datadome=xyz") == {"SESSabc": "123", "datadome": "xyz"}
    with pytest.raises(ValueError):
        parse_cookie_header("   ")


def test_cookie_candidates():
    from custom_components.tenup.api import SESSION_COOKIE_NAMES, cookie_candidates

    assert cookie_candidates("SESSabc=123") == ["SESSabc=123"]
    assert cookie_candidates("Cookie: SESSabc=123; datadome=x") == ["SESSabc=123; datadome=x"]
    bare = cookie_candidates("  abc-DEF_123\n")
    assert bare == [f"{name}=abc-DEF_123" for name in SESSION_COOKIE_NAMES]
    assert bare[0].startswith("SSESS7ba44afc36c80c3faa2b8fa87e7742c5=")
    assert bare[1].startswith("SESS7ba44afc36c80c3faa2b8fa87e7742c5=")
    assert len(bare) == 10
    with pytest.raises(ValueError):
        cookie_candidates("not a cookie value!")
    with pytest.raises(ValueError):
        cookie_candidates("   ")


CURL_PASTE = """curl 'https://tenup.fft.fr/recherche/875800/disponibilites?date=2026-09-12' \\
  -H 'accept: text/html,application/xhtml+xml' \\
  -H 'accept-language: fr-FR,fr;q=0.9' \\
  -b 'datadome=9vKq~Nope; SSESS7ba44afc36c80c3faa2b8fa87e7742c5=aBcD-eF_1234; _ga=GA1.2.7' \\
  -H 'user-agent: Mozilla/5.0' """


def test_cookie_candidates_accepts_a_copy_as_curl_paste():
    """One right-click in the Network tab must be enough: no cookie hunting."""
    from custom_components.tenup.api import cookie_candidates

    assert cookie_candidates(CURL_PASTE) == [
        "SSESS7ba44afc36c80c3faa2b8fa87e7742c5=aBcD-eF_1234"
    ]


def test_cookie_candidates_drops_everything_but_the_session_cookie():
    """A pasted request carries datadome, analytics and the URL: none is stored."""
    from custom_components.tenup.api import cookie_candidates

    only = cookie_candidates(CURL_PASTE)[0]
    for leak in ("datadome", "9vKq", "_ga", "GA1.2.7", "user-agent", "tenup.fft.fr"):
        assert leak not in only, leak


def test_cookie_candidates_extracts_an_unknown_domain_hash():
    """The FFT may re-host the site: match the shape, not the known hashes."""
    from custom_components.tenup.api import SESSION_COOKIE_NAMES, cookie_candidates

    name = "SSESS0123456789abcdef0123456789abcdef"
    assert name not in SESSION_COOKIE_NAMES
    assert cookie_candidates(f"-H 'cookie: {name}=zZz9'") == [f"{name}=zZz9"]


def test_cookie_candidates_deduplicates_a_repeated_cookie():
    """Chrome writes the cookie in both -b and -H 'cookie:'; try it once."""
    from custom_components.tenup.api import cookie_candidates

    pair = "SSESS7ba44afc36c80c3faa2b8fa87e7742c5=dup1"
    assert cookie_candidates(f"-b '{pair}' -H 'cookie: {pair}'") == [pair]


def test_cookie_candidates_keeps_a_plain_header_untouched():
    """No Drupal cookie in sight: the old behaviour must survive."""
    from custom_components.tenup.api import cookie_candidates

    assert cookie_candidates("Cookie: SESSabc=123; datadome=x") == ["SESSabc=123; datadome=x"]




def test_friend_list_is_cleaned_before_being_stored():
    """Short entries are the trap: Ten'Up labels club lessons with first names."""
    from custom_components.tenup.websocket import MAX_FRIENDS, clean_friends

    assert clean_friends(["  BLACKWELL  ", "Dyer"]) == ["BLACKWELL", "Dyer"]
    assert clean_friends(["Van   Dyke"]) == ["Van Dyke"], "inner spaces collapse"
    assert clean_friends(["Hale", "HALE", "hale"]) == ["Hale"], "case-insensitive de-dup"
    assert clean_friends(["", "  ", "a", "ab"]) == [], "nothing usable survives"
    assert clean_friends(["abc"]) == ["abc"], "three characters is the floor"
    assert len(clean_friends([f"ami{n}" for n in range(MAX_FRIENDS + 20)])) == MAX_FRIENDS


SHARED = "SHARED_SESSION_DRUPAL=aae6fe4e-0700-49d0-84ea-7b283f14affa"
SSESS = "SSESS7ba44afc36c80c3faa2b8fa87e7742c5=Kj3-nV_9xQp2"


def test_cookie_candidates_extracts_the_shared_cookie():
    """It is not HttpOnly, so it is the one a bookmarklet can hand over."""
    from custom_components.tenup.api import cookie_candidates

    assert cookie_candidates(f"-b 'datadome=x; {SHARED}; _ga=1'") == [SHARED]


def test_cookie_candidates_prefers_the_shared_cookie_over_the_session_one():
    """Both are valid, but only the shared one survives the Drupal session."""
    from custom_components.tenup.api import cookie_candidates

    assert cookie_candidates(f"-b '{SSESS}; {SHARED}'") == [SHARED, SSESS]


def test_cookie_candidates_reads_a_bare_uuid_as_the_shared_cookie():
    """Pasting just the value must not send a UUID as a Drupal session id."""
    from custom_components.tenup.api import cookie_candidates

    got = cookie_candidates("  aae6fe4e-0700-49d0-84ea-7b283f14affa \n")
    assert got[0] == SHARED


def test_cookie_candidates_still_maps_a_bare_non_uuid_to_the_session_names():
    from custom_components.tenup.api import SHARED_COOKIE_NAME, cookie_candidates

    got = cookie_candidates("abc-DEF_123")
    assert not any(c.startswith(SHARED_COOKIE_NAME) for c in got)
