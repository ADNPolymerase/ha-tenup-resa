"""HTTP client for the Ten'Up member area."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import quote, urlencode, urljoin, urlsplit

import aiohttp
from yarl import URL

from .const import BASE_URL, PUBLIC_API, QUEUE_ENQUEUE_URL, QUEUE_HOST, USER_AGENT
from .parser import (
    BookingForm,
    Planning,
    Slot,
    TenupParseError,
    extract_drupal_settings,
    free_formulas,
    interstitial_reason,
    is_logged_in,
    looks_signed_out,
    parse_booking_form,
    parse_formules_response,
    parse_messages,
    parse_partner_results,
    parse_planning,
    partner_search_term,
    resolve_partner,
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


# Drupal 7 names its session cookie SESS + sha256(cookie domain)[:32], with an
# SSESS prefix when the site is served over HTTPS. Ten'Up sets it on ".fft.fr"
# (observed: SSESS7ba44afc36c80c3faa2b8fa87e7742c5); the other domains are kept
# in case the FFT changes its setup. Tried in order when the user pastes only the value.
_DOMAIN_HASHES = (
    "7ba44afc36c80c3faa2b8fa87e7742c5",  # .fft.fr
    "cb2134c30942b300c65ef3e7a0cb8122",  # tenup.fft.fr
    "299a1e3cc7881f012747993f99f66379",  # .tenup.fft.fr
    "92f2eb7df5a16f11bfa33ba3b3d183bd",  # fft.fr
    "a3f3c315059fce3e5cba5addd6cfa12b",  # www.tenup.fft.fr
)
SESSION_COOKIE_NAMES = tuple(f"{prefix}{h}" for h in _DOMAIN_HASHES for prefix in ("SSESS", "SESS"))

# Any Drupal 7 session cookie, whatever the domain hash, wherever it sits: the
# user can paste a whole "Copy as cURL" command instead of hunting for the
# value in the cookie storage view. The value stops at the first separator a
# shell or a header would use.
# Ten'Up bridges its Nuxt front and its Drupal back with a second cookie, which
# is NOT HttpOnly and outlives the Drupal session by about a month. On its own it
# is enough for Drupal to open a session, so it is the credential worth keeping:
# the user can copy it without the developer tools, and Home Assistant mints a
# fresh SSESS from it whenever it needs one.
SHARED_COOKIE_NAME = "SHARED_SESSION_DRUPAL"
_COOKIE_RE = re.compile(
    r"\b(SHARED_SESSION_DRUPAL|S?SESS[0-9a-f]{32})=([^;,'\"\s]+)"
)
_SESSION_NAME_RE = re.compile(r"S?SESS[0-9a-f]{32}\Z")
_UUID_RE = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\Z")


def _clean_cookie_text(raw: str) -> str:
    text = " ".join(raw.replace("\r", " ").replace("\n", " ").split())
    if text.lower().startswith("cookie:"):
        text = text[7:].strip()
    return text.strip().strip('"').strip("'").strip()


def cookie_candidates(raw: str) -> list[str]:
    """Return the ``name=value`` strings to try for what the user pasted.

    A Drupal session cookie is pulled out of whatever it is buried in, so a
    whole ``Copy as cURL`` command or a request headers dump can be pasted as
    is. ``SESSxxx=yyy`` and full ``Cookie:`` headers are returned unchanged,
    and a bare value (no ``=``) is combined with the known cookie names.
    """
    text = _clean_cookie_text(raw)
    if not text:
        raise ValueError("no cookie found")
    found: list[str] = []
    for name, value in _COOKIE_RE.findall(text):
        pair = f"{name}={value}"
        if pair not in found:
            found.append(pair)
    if found:
        # The shared cookie lives longer, so try it first: it is the one we keep.
        found.sort(key=lambda pair: not pair.startswith(f"{SHARED_COOKIE_NAME}="))
        return found
    if "=" in text:
        return [text]
    if not text.replace("-", "").replace("_", "").isalnum():
        raise ValueError("not a cookie value")
    names = list(SESSION_COOKIE_NAMES)
    if _UUID_RE.match(text):
        # A bare UUID can only be the shared cookie.
        names.insert(0, SHARED_COOKIE_NAME)
    return [f"{name}={text}" for name in names]


def parse_cookie_header(raw: str) -> dict[str, str]:
    """Accept ``SESSxxx=yyy`` or a whole ``Cookie:`` header, return name -> value."""
    text = _clean_cookie_text(raw)
    cookie: SimpleCookie = SimpleCookie()
    cookie.load(text)
    values = {name: morsel.value for name, morsel in cookie.items()}
    if not values:
        raise ValueError("no cookie found")
    return values


def new_cookie_jar() -> aiohttp.CookieJar:
    """A jar for a dedicated Ten'Up session (never share HA's default session: cookies)."""
    return aiohttp.CookieJar()


def new_session() -> aiohttp.ClientSession:
    """A dedicated, self-managed aiohttp session with its own cookie jar.

    We manage its lifecycle ourselves (close it on unload / after validation),
    so it must NOT come from ``async_create_clientsession`` — closing one of those
    trips Home Assistant's "integration closes the HA aiohttp session" warning.
    Must be called from within a running event loop.
    """
    return aiohttp.ClientSession(cookie_jar=new_cookie_jar())


# What RechercheJoueurAutocomplete actually calls: it ignores the
# autocomplete_path the page advertises and hardcodes this one.
JOUEUR_AUTOCOMPLETE_PATH = "/club/autocomplete/partenaire"


_PARTNER_CHOICE_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<ident>\d+)\)\s*$")


def parse_partner_choice(label: str) -> tuple[str, str] | None:
    """Split an autocomplete key: 'John DOE (111111111)' -> name + Ten'Up member id.

    The autocomplete answers {key: display}, and the key is what the field
    submits, so it carries the identifier that tells two homonyms apart.
    """
    match = _PARTNER_CHOICE_RE.match(label.strip())
    if match is None:
        return None
    return match.group("name").strip(), match.group("ident")


def formule_ajax_payload(
    ajax_params: dict[str, Any], user_id: str, current_formule: str = ""
) -> dict[str, str]:
    """The body fetchUserFormule sends, verbatim.

    postParams = {userId, currentFormule} merged with params_formule_joueur_ajax,
    then url is removed and used as the address. qs.stringify renders booleans
    as true/false, so match that rather than Python's True/False.
    """
    payload: dict[str, str] = {
        "userId": str(user_id),
        "currentFormule": str(current_formule or ""),
    }
    for key, value in ajax_params.items():
        if key == "url" or value is None:
            continue
        if value is True:
            payload[key] = "true"
        elif value is False:
            payload[key] = "false"
        else:
            payload[key] = str(value)
    return payload


class TenupClient:
    """Talk to tenup.fft.fr with a user-provided session cookie.

    ``session`` must be a dedicated ``aiohttp.ClientSession`` created with its own
    cookie jar (see ``new_cookie_jar``): the Ten'Up cookies live in that jar.
    """

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
        self._jar = session.cookie_jar
        self.set_cookie(cookie)

    @property
    def session(self) -> aiohttp.ClientSession:
        """The dedicated session (it carries the Ten'Up cookies)."""
        return self._session

    @property
    def session_cookie(self) -> str | None:
        """The session cookie the jar holds now, as ``name=value``.

        Ten'Up can hand out a new session id while we are using it (Drupal
        regenerates one on its own terms). The jar follows, but the config entry
        would still hold the value the user pasted, and the next restart of Home
        Assistant would go back to it and ask for a cookie that never expired.
        """
        fallback: str | None = None
        for morsel in self._jar:
            if not morsel.value:
                continue
            if morsel.key == SHARED_COOKIE_NAME:
                return f"{morsel.key}={morsel.value}"
            if _SESSION_NAME_RE.match(morsel.key) and fallback is None:
                fallback = f"{morsel.key}={morsel.value}"
        return fallback

    # ------------------------------------------------------------------ session
    def set_cookie(self, cookie: str) -> None:
        """Replace the session cookie(s)."""
        values = parse_cookie_header(cookie)
        self._jar.clear()
        self._jar.update_cookies(values, URL(BASE_URL))
        # Ten'Up sets its session cookie on .fft.fr: make it available to every host there.
        self._jar.update_cookies(values, URL("https://fft.fr"))

    @property
    def club_code(self) -> str:
        return self._club_code

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        data: dict[str, str] | str | None = None,
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
        if is_logged_in(body):
            return body, final_url
        # Only a Drupal page that says so proves the cookie is dead. Ten'Up also
        # answers ordinary requests with a Queue-it waiting room or a bot
        # challenge, and treating those as an expired session tore the entry
        # down and made the user paste a new cookie for nothing.
        if looks_signed_out(body):
            raise TenupAuthError("Ten'Up session is not logged in (cookie expired?)")
        raise TenupConnectionError(
            f"Ten'Up answered with {interstitial_reason(body, str(final_url))} on {path}"
        )

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

    async def async_required_players(self, book_path: str) -> int | None:
        """Best-effort: how many players a slot's booking configuration requires.

        Returns None when it can't be determined (parse/connection hiccup); the
        caller caches the result per idCreneau so this runs at most once per config.
        """
        try:
            body, _ = await self._get_html(book_path)
            return parse_booking_form(body).required_players
        except (TenupParseError, TenupError):
            return None

    async def async_search_partner(self, query: str) -> list[tuple[str, str]]:
        """Search a club member to play with, the way the site's own field does."""
        wanted = " ".join(query.split())
        if len(wanted) < 3:
            raise TenupBookingError("Indiquez au moins 3 caracteres pour chercher un partenaire")
        # Ten'Up searches ONE word: "Do eric" answers nothing at all, while
        # "Do" answers both DOE. So send a single term, then narrow the
        # answer with everything that was typed.
        term = partner_search_term(wanted)
        text, _final, status = await self._request(
            "GET",
            f"{BASE_URL}{JOUEUR_AUTOCOMPLETE_PATH}/{quote(term, safe='')}",
            headers=_JSON_HEADERS,
        )
        if status >= 500:
            raise TenupConnectionError(f"Ten'Up answered {status} on the partner search")
        results = parse_partner_results(text)
        if len(wanted.split()) > 1:
            # Keep the wider list when nothing matches, rather than show nothing.
            return resolve_partner(results, wanted) or results
        return results

    async def async_partner_formulas(
        self, book_path: str, user_id: str
    ) -> list[dict[str, Any]]:
        """Formulas Ten'Up opens to that partner, paid ones removed."""
        body, _ = await self._get_html(book_path)
        settings = extract_drupal_settings(body)
        params = (settings.get("reservation_detail") or {}).get(
            "params_formule_joueur_ajax"
        ) or {}
        text, _final, status = await self._request(
            "POST",
            f"{BASE_URL}/club/reservations/formule/ajax",
            headers={
                **_JSON_HEADERS,
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": BASE_URL,
                "Referer": urljoin(BASE_URL, book_path),
                "X-Requested-With": "XMLHttpRequest",
            },
            data=formule_ajax_payload(params, user_id),
        )
        if status >= 500:
            raise TenupConnectionError(f"Ten'Up answered {status} on formule/ajax")
        return free_formulas(parse_formules_response(text))

    async def async_book(
        self,
        slot: Slot,
        partner_choice: str | None = None,
        partner_formula: str | None = None,
    ) -> str:
        """Book a free slot. Returns the confirmation text.

        A slot that demands two players needs partner_choice, the autocomplete
        key that carries the Ten'Up member id.
        """
        form = await self.async_get_booking_form(slot)
        if form.required_players > 1 and not partner_choice:
            raise TenupBookingError(
                f"Ce créneau demande {form.required_players} joueurs; "
                "indiquez un partenaire"
            )
        if partner_choice:
            form.partner_choice = partner_choice
            form.partner_formula = partner_formula
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
