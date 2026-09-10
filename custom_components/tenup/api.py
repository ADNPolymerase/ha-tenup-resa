"""HTTP client for the Ten'Up member area."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import urljoin, urlsplit

import aiohttp
from yarl import URL

from .const import BASE_URL, PUBLIC_API, QUEUE_ENQUEUE_URL, QUEUE_HOST, USER_AGENT
from .parser import (
    BookingForm,
    Planning,
    Slot,
    TenupParseError,
    is_logged_in,
    parse_booking_form,
    parse_messages,
    parse_planning,
)

_LOGGER = logging.getLogger(__name__)

_HTML_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9",
}
_JSON_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
    "Accept-Language": "fr-FR,fr;q=0.9",
}
_TIMEOUT = aiohttp.ClientTimeout(total=30)


class TenupError(Exception):
    """Base error."""


class TenupConnectionError(TenupError):
    """Ten'Up could not be reached or answered something unexpected."""


class TenupAuthError(TenupError):
    """The session cookie is missing, expired or not logged in."""


class TenupBookingError(TenupError):
    """Ten'Up refused a booking or a cancellation, with its own message."""


# Drupal 7 names its session cookie SESS + sha256(cookie domain)[:32]. Ten'Up may
# be configured with or without the leading dot, so both are tried when the user
# pastes only the value.
SESSION_COOKIE_NAMES = (
    "SESScb2134c30942b300c65ef3e7a0cb8122",  # tenup.fft.fr
    "SESS299a1e3cc7881f012747993f99f66379",  # .tenup.fft.fr
    "SESSa3f3c315059fce3e5cba5addd6cfa12b",  # www.tenup.fft.fr
    "SESS7ba44afc36c80c3faa2b8fa87e7742c5",  # .fft.fr
    "SESS92f2eb7df5a16f11bfa33ba3b3d183bd",  # fft.fr
)


def _clean_cookie_text(raw: str) -> str:
    text = " ".join(raw.replace("\r", " ").replace("\n", " ").split())
    if text.lower().startswith("cookie:"):
        text = text[7:].strip()
    return text.strip().strip('"').strip("'").strip()


def cookie_candidates(raw: str) -> list[str]:
    """Return the ``name=value`` strings to try for what the user pasted.

    ``SESSxxx=yyy`` and full ``Cookie:`` headers are returned as is. A bare value
    (no ``=``) is combined with the known Drupal session cookie names.
    """
    text = _clean_cookie_text(raw)
    if not text:
        raise ValueError("no cookie found")
    if "=" in text:
        return [text]
    if not text.replace("-", "").replace("_", "").isalnum():
        raise ValueError("not a cookie value")
    return [f"{name}={text}" for name in SESSION_COOKIE_NAMES]


def parse_cookie_header(raw: str) -> dict[str, str]:
    """Accept ``SESSxxx=yyy`` or a whole ``Cookie:`` header, return name -> value."""
    text = _clean_cookie_text(raw)
    cookie: SimpleCookie = SimpleCookie()
    cookie.load(text)
    values = {name: morsel.value for name, morsel in cookie.items()}
    if not values:
        raise ValueError("no cookie found")
    return values


class TenupClient:
    """Talk to tenup.fft.fr with a user-provided session cookie."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        cookie: str,
        club_code: str,
        tzinfo: Any,
    ) -> None:
        self._session = session
        self._club_code = str(club_code)
        self._tzinfo = tzinfo
        self._queue_lock = asyncio.Lock()
        self._jar = aiohttp.CookieJar()
        self.set_cookie(cookie)

    # ------------------------------------------------------------------ session
    def set_cookie(self, cookie: str) -> None:
        """Replace the session cookie(s)."""
        values = parse_cookie_header(cookie)
        self._jar.clear()
        self._jar.update_cookies(values, URL(BASE_URL))

    @property
    def club_code(self) -> str:
        return self._club_code

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        data: dict[str, str] | None = None,
        allow_redirects: bool = True,
        _queue_retry: bool = True,
    ) -> tuple[str, URL, int]:
        """Return (body, final_url, status), passing the Queue-it waiting room if needed."""
        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                data=data,
                allow_redirects=allow_redirects,
                cookie_jar=self._jar,
                timeout=_TIMEOUT,
            ) as resp:
                body = await resp.text()
                final_url = resp.url
                status = resp.status
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise TenupConnectionError(f"{method} {url}: {err}") from err

        if QUEUE_HOST in (final_url.host or "") and _queue_retry:
            _LOGGER.debug("Queue-it in front of %s, requesting a token", url)
            await self._pass_queue(url)
            return await self._request(
                method,
                url,
                headers=headers,
                data=data,
                allow_redirects=allow_redirects,
                _queue_retry=False,
            )
        if QUEUE_HOST in (final_url.host or ""):
            raise TenupConnectionError("Ten'Up waiting room could not be passed")
        return body, final_url, status

    async def _pass_queue(self, target_url: str) -> None:
        """Ask Queue-it for a safety-net token (idle queue) and redeem it."""
        async with self._queue_lock:
            payload = {
                "layoutName": "tenup prod",
                "customUrlParams": "",
                "targetUrl": target_url,
                "Referrer": "",
            }
            try:
                async with self._session.post(
                    QUEUE_ENQUEUE_URL,
                    json=payload,
                    headers={
                        **_JSON_HEADERS,
                        "Origin": "https://tenup.queue-it.net",
                        "Referer": "https://tenup.queue-it.net/",
                    },
                    cookie_jar=self._jar,
                    timeout=_TIMEOUT,
                ) as resp:
                    data = await resp.json(content_type=None)
                redirect = data.get("redirectUrl") or data.get("RedirectUrl")
                if not redirect:
                    raise TenupConnectionError(f"Queue-it did not return a token: {data}")
                async with self._session.get(
                    redirect,
                    headers=_HTML_HEADERS,
                    allow_redirects=True,
                    cookie_jar=self._jar,
                    timeout=_TIMEOUT,
                ) as resp:
                    await resp.read()
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                raise TenupConnectionError(f"Queue-it: {err}") from err

    async def _get_html(self, path: str) -> tuple[str, URL]:
        body, final_url, status = await self._request(
            "GET", urljoin(BASE_URL, path), headers=_HTML_HEADERS
        )
        if status >= 500:
            raise TenupConnectionError(f"Ten'Up answered {status} on {path}")
        if not is_logged_in(body):
            raise TenupAuthError("Ten'Up session is not logged in (cookie expired?)")
        return body, final_url

    # ----------------------------------------------------------------- planning
    async def async_get_planning(self, day: date) -> Planning:
        """The reservation grid of ``day``."""
        path = f"/club/{self._club_code}/reservations/{day:%Y%m%d}"
        body, _ = await self._get_html(path)
        planning = parse_planning(body, day, self._tzinfo)
        if not planning.slots and "Accès refusé" in body:
            raise TenupAuthError("Ten'Up refused access to the club planning")
        return planning

    async def async_validate(self) -> Planning:
        """Fetch today's planning; raises TenupAuthError on a bad cookie."""
        return await self.async_get_planning(datetime.now(self._tzinfo).date())

    # ------------------------------------------------------------------ booking
    async def async_get_booking_form(self, slot: Slot) -> BookingForm:
        """Open the reservation detail page of a free slot."""
        if not slot.book_path:
            raise TenupBookingError("This slot has no booking link (not free)")
        body, final_url = await self._get_html(slot.book_path)
        try:
            return parse_booking_form(body)
        except TenupParseError as err:
            messages = parse_messages(body)
            if messages:
                raise TenupBookingError(" ".join(messages)) from err
            raise TenupConnectionError(
                f"Unexpected reservation detail page at {final_url.path}: {err}"
            ) from err

    async def async_book(self, slot: Slot) -> str:
        """Book a free slot for the account owner alone. Returns the confirmation text."""
        form = await self.async_get_booking_form(slot)
        if form.required_players > 1:
            raise TenupBookingError(
                f"Ce créneau demande {form.required_players} joueurs; "
                "l'ajout d'un partenaire n'est pas encore pris en charge"
            )
        body, final_url, status = await self._request(
            "POST",
            f"{BASE_URL}/club/reservations/detail/submit",
            headers={
                **_HTML_HEADERS,
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": BASE_URL,
                "Referer": urljoin(BASE_URL, slot.book_path or "/"),
            },
            data=form.as_post_data(),
        )
        if status >= 500:
            raise TenupConnectionError(f"Ten'Up answered {status} on booking submit")
        if not is_logged_in(body):
            raise TenupAuthError("Session lost while booking")
        if "/club/reservations/confirmation" in final_url.path:
            return "Votre réservation est confirmée."
        messages = parse_messages(body)
        raise TenupBookingError(
            " ".join(messages) if messages else f"Ten'Up did not confirm (landed on {final_url.path})"
        )

    async def async_cancel(self, slot: Slot) -> None:
        """Cancel one of the account owner's reservations (a plain GET on Ten'Up)."""
        if not slot.cancel_path:
            raise TenupBookingError("This slot has no cancellation link (not yours)")
        body, final_url = await self._get_html(slot.cancel_path)
        messages = parse_messages(body)
        errors = [m for m in messages if "impossible" in m.lower() or "erreur" in m.lower()]
        if errors:
            raise TenupBookingError(" ".join(errors))

    # --------------------------------------------------------------- public API
    @staticmethod
    async def async_search_clubs(
        session: aiohttp.ClientSession, query: str, practice: str = "TENNIS"
    ) -> list[dict[str, Any]]:
        """Public club search (no authentication)."""
        payload = {"query": query, "pratique": practice, "from": 0, "size": 10}
        try:
            async with session.post(
                f"{PUBLIC_API}/clubs/recherche",
                json=payload,
                headers=_JSON_HEADERS,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status != 200:
                    raise TenupConnectionError(f"club search answered {resp.status}")
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise TenupConnectionError(f"club search: {err}") from err
        return list(data.get("clubs") or [])

    @staticmethod
    def host_of(url: str) -> str:
        return urlsplit(url).netloc
