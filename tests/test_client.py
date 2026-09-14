"""Exercise TenupClient against a fake aiohttp session (kwargs, cookies, Queue-it, auth)."""
import asyncio
from datetime import date, timedelta, timezone
from pathlib import Path

import aiohttp
import pytest
from yarl import URL

from custom_components.tenup.api import TenupAuthError, TenupBookingError, TenupClient, TenupConnectionError

FIXTURES = Path(__file__).parent / "fixtures"
TZ = timezone(timedelta(hours=2))
PLANNING = (FIXTURES / "planning.html").read_text(encoding="utf-8")


class FakeResponse:
    def __init__(self, body, url, status=200):
        self._body, self.url, self.status = body, URL(url), status

    async def text(self):
        return self._body

    async def read(self):
        return self._body.encode()

    async def json(self, content_type=None):
        import json
        return json.loads(self._body)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Only what TenupClient uses: request/get/post + a real CookieJar."""

    def __init__(self, routes):
        self.cookie_jar = aiohttp.CookieJar()
        self.routes = routes   # (method, url substring) -> list of FakeResponse, popped in order
        self.calls = []

    def _find(self, method, url, kwargs):
        self.calls.append((method, str(url), kwargs))
        for (m, part), responses in self.routes.items():
            if m == method and part in str(url):
                return responses.pop(0) if len(responses) > 1 else responses[0]
        raise AssertionError(f"unexpected {method} {url}")

    def request(self, method, url, **kwargs):
        return self._find(method, url, kwargs)

    def get(self, url, **kwargs):
        return self._find("GET", url, kwargs)

    def post(self, url, **kwargs):
        return self._find("POST", url, kwargs)


def run(fn):
    """aiohttp's CookieJar needs a running loop: build everything inside one."""
    return asyncio.run(fn())


def test_cookie_lands_in_the_jar():
    async def main():
        session = FakeSession({})
        TenupClient(session, "SSESSabc=xyz", "87654321", TZ)
        return {c.key for c in session.cookie_jar}
    assert run(main) == {"SSESSabc"}


def test_planning_request_passes_only_supported_kwargs():
    async def main():
        session = FakeSession({("GET", "/club/87654321/reservations/20260910"): [
            FakeResponse(PLANNING, "https://tenup.fft.fr/club/87654321/reservations/20260910")]})
        client = TenupClient(session, "SSESSabc=xyz", "87654321", TZ)
        planning = await client.async_get_planning(date(2026, 9, 10))
        return planning, session.calls
    planning, calls = run(main)
    assert len(planning.courts) == 2
    method, url, kwargs = calls[0]
    assert method == "GET" and url.endswith("/reservations/20260910")
    assert set(kwargs) <= {"headers", "data", "allow_redirects", "timeout"}, kwargs


def test_not_logged_in_raises_auth_error():
    async def main():
        body = PLANNING.replace("logged-in", "not-logged-in")
        session = FakeSession({("GET", "/reservations/"): [FakeResponse(body, "https://tenup.fft.fr/club/87654321/reservations/20260910", 403)]})
        client = TenupClient(session, "SSESSabc=xyz", "87654321", TZ)
        await client.async_get_planning(date(2026, 9, 10))
    with pytest.raises(TenupAuthError):
        run(main)


def test_queue_it_is_passed_once_then_retried():
    async def main():
        session = FakeSession({
            ("GET", "/reservations/"): [
                FakeResponse("<html>queue</html>", "https://tenup.queue-it.net/?c=tenup"),
                FakeResponse(PLANNING, "https://tenup.fft.fr/club/87654321/reservations/20260910"),
            ],
            ("POST", "queue-it.net/spa-api"): [FakeResponse('{"redirectUrl": "https://tenup.fft.fr/x?queueittoken=abc"}', "https://tenup.queue-it.net/spa-api")],
            ("GET", "queueittoken=abc"): [FakeResponse("", "https://tenup.fft.fr/x")],
        })
        client = TenupClient(session, "SSESSabc=xyz", "87654321", TZ)
        planning = await client.async_get_planning(date(2026, 9, 10))
        return planning, session.calls
    planning, calls = run(main)
    assert len(planning.slots) == 7
    assert calls[1][0] == "POST" and "spa-api" in calls[1][1]
    assert len(calls) == 4


def test_queue_it_that_never_opens_is_an_error():
    async def main():
        session = FakeSession({
            ("GET", "/reservations/"): [FakeResponse("<html>queue</html>", "https://tenup.queue-it.net/?c=tenup")],
            ("POST", "queue-it.net/spa-api"): [FakeResponse('{"redirectUrl": "https://tenup.fft.fr/x?queueittoken=abc"}', "https://tenup.queue-it.net/spa-api")],
            ("GET", "queueittoken=abc"): [FakeResponse("", "https://tenup.fft.fr/x")],
        })
        client = TenupClient(session, "SSESSabc=xyz", "87654321", TZ)
        await client.async_get_planning(date(2026, 9, 10))
    with pytest.raises(TenupConnectionError):
        run(main)


def test_required_players_reads_the_booking_form():
    async def main():
        detail = (FIXTURES / "detail.html").read_text(encoding="utf-8")
        session = FakeSession({("GET", "/reservation_court_add/"): [
            FakeResponse(detail, "https://tenup.fft.fr/club/reservation_court_add/nojs/21100/56152/1/2")]})
        client = TenupClient(session, "SSESSabc=xyz", "87654321", TZ)
        return await client.async_required_players("/club/reservation_court_add/nojs/21100/56152/1/2")
    assert run(main) == 1  # detail.html fixture asks for 1 player


def test_required_players_is_none_on_garbage():
    async def main():
        session = FakeSession({("GET", "/reservation_court_add/"): [
            FakeResponse("<html><body class='logged-in'>nope</body></html>", "https://tenup.fft.fr/x")]})
        client = TenupClient(session, "SSESSabc=xyz", "87654321", TZ)
        return await client.async_required_players("/club/reservation_court_add/nojs/9/9/1/2")
    assert run(main) is None


QUEUE_BODY = ('<!doctype html><html><head>'
              '<script src="https://static.queue-it.net/script/queueclient.min.js"></script>'
              '</head><body><div>file d\'attente</div></body></html>')
BOT_BODY = ('<!doctype html><html><head>'
            '<script src="https://ct.captcha-delivery.com/c.js"></script>'
            '</head><body><div id="datadome-captcha"></div></body></html>')


@pytest.mark.parametrize("body, wall", [(QUEUE_BODY, "Queue-it"), (BOT_BODY, "bot challenge")])
def test_an_interstitial_is_transient_not_an_expired_cookie(body, wall):
    """Ten'Up serves these from its own host, so the queue-host check misses them.

    They used to raise TenupAuthError, which HA turns into ConfigEntryAuthFailed:
    the entry was torn down and a fresh cookie demanded although the session was
    still perfectly valid.
    """
    async def main():
        session = FakeSession({("GET", "/reservations/"): [
            FakeResponse(body, "https://tenup.fft.fr/club/87654321/reservations/20260910")]})
        client = TenupClient(session, "SSESSabc=xyz", "87654321", TZ)
        await client.async_get_planning(date(2026, 9, 10))

    with pytest.raises(TenupConnectionError) as excinfo:
        run(main)
    assert wall in str(excinfo.value)
    # and emphatically not the fatal one
    assert not isinstance(excinfo.value, TenupAuthError)


def test_a_signed_out_drupal_page_still_raises_auth_error():
    """The one case that really does need a new cookie must keep working."""
    async def main():
        body = '<!doctype html><html><body class="html not-logged-in">Connexion</body></html>'
        session = FakeSession({("GET", "/reservations/"): [
            FakeResponse(body, "https://tenup.fft.fr/club/87654321/reservations/20260910")]})
        client = TenupClient(session, "SSESSabc=xyz", "87654321", TZ)
        await client.async_get_planning(date(2026, 9, 10))
    with pytest.raises(TenupAuthError):
        run(main)


REAL_NAME = "SSESS7ba44afc36c80c3faa2b8fa87e7742c5"


def test_session_cookie_reports_what_the_jar_holds():
    async def main():
        session = FakeSession({})
        client = TenupClient(session, f"{REAL_NAME}=pasted", "87654321", TZ)
        return client.session_cookie
    assert run(main) == f"{REAL_NAME}=pasted"


def test_session_cookie_follows_a_rotation_by_tenup():
    """Drupal can hand out a new session id mid-flight: the config entry must follow."""
    async def main():
        session = FakeSession({})
        client = TenupClient(session, f"{REAL_NAME}=old", "87654321", TZ)
        session.cookie_jar.update_cookies(
            {REAL_NAME: "rotated"}, URL("https://tenup.fft.fr")
        )
        return client.session_cookie
    assert run(main) == f"{REAL_NAME}=rotated"


def test_session_cookie_ignores_the_other_cookies():
    """datadome and Queue-it also live in the jar and must never be saved as the session."""
    async def main():
        session = FakeSession({})
        client = TenupClient(session, f"{REAL_NAME}=mine", "87654321", TZ)
        session.cookie_jar.update_cookies(
            {"datadome": "abc", "QueueITAccepted": "1", "_ga": "GA1.2"},
            URL("https://tenup.fft.fr"),
        )
        return client.session_cookie
    assert run(main) == f"{REAL_NAME}=mine"


def test_session_cookie_is_none_without_a_drupal_session():
    """A jar with no Drupal cookie must not make the coordinator overwrite anything."""
    async def main():
        session = FakeSession({})
        client = TenupClient(session, "SSESSabc=xyz", "87654321", TZ)
        return client.session_cookie
    assert run(main) is None


SHARED_NAME = "SHARED_SESSION_DRUPAL"
SHARED_VALUE = "aae6fe4e-0700-49d0-84ea-7b283f14affa"


def test_session_cookie_prefers_the_shared_cookie():
    """Drupal mints a new SSESS on every start: it must never replace the durable one."""
    async def main():
        session = FakeSession({})
        client = TenupClient(session, f"{SHARED_NAME}={SHARED_VALUE}", "87654321", TZ)
        session.cookie_jar.update_cookies(
            {REAL_NAME: "minted-by-drupal"}, URL("https://tenup.fft.fr")
        )
        return client.session_cookie
    assert run(main) == f"{SHARED_NAME}={SHARED_VALUE}"


def test_session_cookie_falls_back_to_ssess_without_a_shared_cookie():
    """Users set up before this existed keep working on their SSESS alone."""
    async def main():
        session = FakeSession({})
        client = TenupClient(session, f"{REAL_NAME}=legacy", "87654321", TZ)
        return client.session_cookie
    assert run(main) == f"{REAL_NAME}=legacy"


# ---------------------------------------------------------------- cancellation
CANCEL_PATH = "/club/reservation_court_delete/nojs/87654321/165841846/21100/2100"
PLANNING_URL = "https://tenup.fft.fr/club/87654321/reservations/20260910"
# What Ten'Up answered a successful cancellation with on 2026-09-14: no body
# class at all, so nothing that says signed in or signed out.
NOT_A_DRUPAL_PAGE = "<!doctype html><html><head></head><div>ok</div></html>"
FREED = PLANNING.replace("adherent-reservation-calendrier-row-mine", "")


def _my_slot():
    from custom_components.tenup.parser import parse_planning

    planning = parse_planning(PLANNING, date(2026, 9, 10), TZ)
    return next(s for s in planning.slots if s.cancel_path)


def _cancel_calls(session):
    return [c for c in session.calls if "/reservation_court_delete/" in c[1]]


def test_a_cancellation_is_judged_on_the_planning_not_on_the_answer_page():
    """The answer page proved nothing and made a real cancellation look failed."""
    async def main():
        session = FakeSession({
            ("GET", "/reservation_court_delete/"): [
                FakeResponse(NOT_A_DRUPAL_PAGE, "https://tenup.fft.fr" + CANCEL_PATH)],
            ("GET", "/reservations/20260910"): [FakeResponse(FREED, PLANNING_URL)],
        })
        client = TenupClient(session, "SSESSabc=xyz", "87654321", TZ)
        await client.async_cancel(_my_slot())
        return session

    session = run(main)
    assert len(_cancel_calls(session)) == 1, "the cancel link is opened once, never retried"


def test_a_cancellation_the_planning_does_not_confirm_is_an_error():
    async def main():
        session = FakeSession({
            ("GET", "/reservation_court_delete/"): [
                FakeResponse(NOT_A_DRUPAL_PAGE, "https://tenup.fft.fr" + CANCEL_PATH)],
            ("GET", "/reservations/20260910"): [FakeResponse(PLANNING, PLANNING_URL)],
        })
        client = TenupClient(session, "SSESSabc=xyz", "87654321", TZ)
        await client.async_cancel(_my_slot())

    with pytest.raises(TenupBookingError):
        run(main)


def test_a_cancellation_on_a_dead_session_still_asks_for_a_cookie():
    """And the planning is not fetched: there is nothing to confirm."""
    async def main():
        body = '<!doctype html><html><body class="html not-logged-in">Connexion</body></html>'
        session = FakeSession({("GET", "/reservation_court_delete/"): [
            FakeResponse(body, "https://tenup.fft.fr" + CANCEL_PATH)]})
        client = TenupClient(session, "SSESSabc=xyz", "87654321", TZ)
        await client.async_cancel(_my_slot())

    with pytest.raises(TenupAuthError):
        run(main)


def test_a_refusal_stated_by_tenup_is_relayed():
    async def main():
        body = ('<!doctype html><html><body class="html logged-in">'
                '<div class="messages error">Annulation impossible hors delai</div></body></html>')
        session = FakeSession({("GET", "/reservation_court_delete/"): [
            FakeResponse(body, "https://tenup.fft.fr" + CANCEL_PATH)]})
        client = TenupClient(session, "SSESSabc=xyz", "87654321", TZ)
        await client.async_cancel(_my_slot())

    with pytest.raises(TenupBookingError) as excinfo:
        run(main)
    assert "impossible" in str(excinfo.value)


def test_an_unconfirmed_cancellation_says_so():
    """The link was opened: the user must not be told Ten'Up is simply down."""
    async def main():
        session = FakeSession({
            ("GET", "/reservation_court_delete/"): [
                FakeResponse(NOT_A_DRUPAL_PAGE, "https://tenup.fft.fr" + CANCEL_PATH)],
            ("GET", "/reservations/20260910"): [FakeResponse(QUEUE_BODY, PLANNING_URL)],
        })
        client = TenupClient(session, "SSESSabc=xyz", "87654321", TZ)
        await client.async_cancel(_my_slot())

    with pytest.raises(TenupConnectionError) as excinfo:
        run(main)
    assert "non confirmée" in str(excinfo.value)
