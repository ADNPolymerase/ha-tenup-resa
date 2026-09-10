"""Exercise TenupClient against a fake aiohttp session (kwargs, cookies, Queue-it, auth)."""
import asyncio
from datetime import date, timedelta, timezone
from pathlib import Path

import aiohttp
import pytest
from yarl import URL

from custom_components.tenup.api import TenupAuthError, TenupClient, TenupConnectionError

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
