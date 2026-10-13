"""HTTP client for the Ten'Up member area.

Ten'Up serves that area as a JSON API behind the browser session cookie, so
everything here is one of two things: carrying that cookie faithfully (and
through the waiting room Ten'Up puts in front of its site), and turning the
answers into the dataclasses of :mod:`models`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import urlencode

import aiohttp
from yarl import URL

from .const import API, BASE_URL, QUEUE_ENQUEUE_URL, QUEUE_HOST, USER_AGENT
from .models import (
    Eligibility,
    Partner,
    Planning,
    Slot,
    TenupParseError,
    eligibility_from_json,
    partner_search_term,
    partners_from_json,
    planning_from_json,
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


# The session cookie of the member area, named by the site's own code. The 2026
# rebuild moved the back end from Drupal to Java and renamed the cookie with it;
# unlike the Drupal one it is HttpOnly, so no bookmarklet can read it and the
# user copies it from the browser's developer tools.
SESSION_COOKIE_NAME = "SHARED_SESSION_JAVA"

# What the previous site used. A browser that has been through the migration
# still carries it, and it is now refused by the API, so it is accepted only as
# a last resort: an installation that predates the rebuild keeps loading, and
# says the session is dead rather than that the cookie is malformed.
SHARED_COOKIE_NAME = "SHARED_SESSION_DRUPAL"

# Drupal 7 named its own session cookie SESS + sha256(cookie domain)[:32], with
# an SSESS prefix over HTTPS. Kept for the same reason, and because an old entry
# may still hold one.
_DOMAIN_HASHES = (
    "7ba44afc36c80c3faa2b8fa87e7742c5",  # .fft.fr
    "cb2134c30942b300c65ef3e7a0cb8122",  # tenup.fft.fr
    "299a1e3cc7881f012747993f99f66379",  # .tenup.fft.fr
    "92f2eb7df5a16f11bfa33ba3b3d183bd",  # fft.fr
    "a3f3c315059fce3e5cba5addd6cfa12b",  # www.tenup.fft.fr
)
# Only these can carry a value that is not a UUID, so a bare paste that is not
# one is tried against them alone.
SESSION_COOKIE_NAMES = tuple(
    f"{prefix}{h}" for h in _DOMAIN_HASHES for prefix in ("SSESS", "SESS")
)

# Any of them, wherever it sits: the user can paste a whole "Copy as cURL"
# command, or the single line the developer tools show, rather than hunt for the
# value. A value stops at the first separator a shell or a header would use.
_COOKIE_RE = re.compile(
    r"\b(SHARED_SESSION_JAVA|SHARED_SESSION_DRUPAL|S?SESS[0-9a-f]{32})=([^;,'\"\s]+)"
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

    The session cookie is pulled out of whatever it is buried in, so a whole
    ``Copy as cURL`` command or a request headers dump can be pasted as is. A
    bare value (no ``=``) is combined with the known cookie names.

    When the paste carries other cookies too, the whole set is kept as a last
    candidate: should Ten'Up one day want a companion cookie alongside the
    session, sending everything the browser sends is what gets through, and the
    user has already handed it over.
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
        # The one the site actually authenticates with comes first, then the one
        # it replaced: the others are only there so an entry made before the 2026
        # rebuild still loads and reports a dead session rather than a bad cookie.
        order = (SESSION_COOKIE_NAME, SHARED_COOKIE_NAME)
        found.sort(
            key=lambda pair: next(
                (i for i, name in enumerate(order) if pair.startswith(f"{name}=")),
                len(order),
            )
        )
        whole = _whole_cookie_set(text)
        if whole and whole not in found:
            found.append(whole)
        return found
    if "=" in text:
        return [text]
    if not text.replace("-", "").replace("_", "").isalnum():
        raise ValueError("not a cookie value")
    names = list(SESSION_COOKIE_NAMES)
    if _UUID_RE.match(text):
        # Both the session cookie and the one it replaced are plain UUIDs.
        names = [SESSION_COOKIE_NAME, SHARED_COOKIE_NAME] + [
            name for name in names if name not in (SESSION_COOKIE_NAME, SHARED_COOKIE_NAME)
        ]
    return [f"{name}={text}" for name in names]


# What a "Copy as cURL" wraps the cookies in. The closing quote may already be
# gone: the text is cleaned of stray quotes before we get here.
_CURL_PREFIX_RE = re.compile(r"^(?:-b|--cookie)\s+'?|^-H\s+'?[Cc]ookie:\s*", re.IGNORECASE)


def _whole_cookie_set(text: str) -> str | None:
    """Every cookie of a ``Copy as cURL`` or a ``Cookie:`` header, as pasted."""
    candidate = _CURL_PREFIX_RE.sub("", text).strip().strip("'").strip('"')
    if ";" in candidate and candidate.count("=") > 1:
        return candidate
    return None


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
        self._me: int | None = None
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
            if morsel.key == SESSION_COOKIE_NAME:
                return f"{morsel.key}={morsel.value}"
            if fallback is None and (
                morsel.key == SHARED_COOKIE_NAME or _SESSION_NAME_RE.match(morsel.key)
            ):
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


    # --------------------------------------------------------------- API calls
    async def _api(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        payload: Any = None,
    ) -> Any:
        """One call to the member API, with its two ways of saying "signed out".

        A dead cookie earns a 401 on the API, but Ten'Up also answers its own
        sign-in page to a request it will not serve, and that page is HTML. Both
        mean the same thing to us, and nothing else does: a waiting room or a bot
        challenge must never be read as an expired session, or the user is asked
        for a new cookie for nothing.
        """
        url = f"{API}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        headers = dict(_JSON_HEADERS)
        data: str | None = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload)

        body, final_url, status = await self._request(
            method, url, headers=headers, data=data
        )

        _LOGGER.debug(
            "Ten'Up %s %s -> %s (%s)", method, path, status, final_url.host
        )
        answer: Any = None
        if body.strip():
            try:
                answer = json.loads(body)
            except ValueError:
                answer = None

        if status in (401, 403) or (answer is None and "/auth/signin" in str(final_url)):
            raise TenupAuthError("Ten'Up session is not logged in (cookie expired?)")
        if status >= 500:
            raise TenupConnectionError(f"Ten'Up answered {status} on {path}")
        if status >= 400:
            message = ""
            if isinstance(answer, dict):
                message = str(answer.get("errorMessage") or answer.get("message") or "")
            if message:
                raise TenupBookingError(message)
            raise TenupConnectionError(f"Ten'Up answered {status} on {path}")
        if answer is None and body.strip():
            raise TenupConnectionError(f"Ten'Up answered no JSON on {path}")
        return answer

    # ------------------------------------------------------------------ profile
    async def async_profile(self) -> dict[str, Any]:
        """The signed-in member. Also the only way to recognise our own bookings."""
        answer = await self._api("GET", "/profil")
        if not isinstance(answer, dict):
            raise TenupConnectionError("Ten'Up answered no profile")
        return answer

    async def async_me(self) -> int | None:
        """Our own member id, fetched once and kept.

        The grid names the players of a reservation by ``idCrm``; the profile
        calls the same number ``id``. Comparing the two is what tells our own
        bookings from everybody else's.
        """
        if self._me is None:
            profile = await self.async_profile()
            raw = profile.get("id")
            self._me = int(raw) if raw is not None else None
        return self._me

    # ----------------------------------------------------------------- planning
    async def async_get_planning(self, day: date) -> Planning:
        """The reservation grid of ``day``."""
        me = await self.async_me()
        answer = await self._api(
            "GET",
            "/clubs/reservations",
            params={"date": day.isoformat(), "codeClub": self._club_code},
        )
        try:
            return planning_from_json(answer, day, self._tzinfo, me)
        except TenupParseError as err:
            raise TenupConnectionError(f"Unexpected planning for {day}: {err}") from err

    async def async_validate(self) -> Planning:
        """Fetch today's planning; raises TenupAuthError on a bad cookie."""
        return await self.async_get_planning(datetime.now(self._tzinfo).date())

    async def async_my_reservations(self) -> list[dict[str, Any]]:
        """Our own reservations, club by club, as Ten'Up lists them."""
        answer = await self._api("GET", "/profil/reservations")
        return answer if isinstance(answer, list) else []

    # -------------------------------------------------------------- eligibility
    async def async_eligibility(
        self, slot: Slot, id_crm: int | None = None
    ) -> Eligibility:
        """What one player may do on one slot.

        Without ``id_crm`` this answers for the signed-in member and carries the
        form; with it, for the partner about to be named, which is how their own
        offers are read.
        """
        payload: dict[str, Any] = {
            "idCourt": int(slot.court_id),
            "codeClub": self._club_code,
            "date": slot.start.date().isoformat(),
            "heureDebut": slot.hhmmss,
            "heureFin": slot.end_hhmmss,
            "formulaire": id_crm is None,
        }
        if id_crm is not None:
            payload["idCrm"] = int(id_crm)
        answer = await self._api(
            "POST", "/clubs/reservations/eligibilite", payload=payload
        )
        try:
            return eligibility_from_json(answer)
        except TenupParseError as err:
            raise TenupConnectionError(f"Unexpected eligibility: {err}") from err

    async def async_required_players(self, slot: Slot) -> int | None:
        """Best-effort: how many players this slot configuration demands.

        Returns None on a hiccup; the caller caches the answer per idCreneau, so
        this runs at most once per slot configuration.
        """
        try:
            return (await self.async_eligibility(slot)).required_players
        except TenupError:
            return None

    # ------------------------------------------------------------------ partner
    async def async_search_partner(self, query: str) -> list[Partner]:
        """Search a club member to play with, the way the site's own field does."""
        wanted = " ".join(query.split())
        if len(wanted) < 3:
            raise TenupBookingError(
                "Indiquez au moins 3 caracteres pour chercher un partenaire"
            )
        # Ten'Up searches one word: "Jean Dupont" answers nothing at all, while
        # "Dupont" answers every Dupont. So send a single term, then narrow the
        # answer with everything that was typed.
        answer = await self._api(
            "POST",
            "/personnes/recherche/reservations-adherents",
            payload={
                "query": partner_search_term(wanted),
                "codesClubs": [self._club_code],
                "from": 0,
                "size": 10,
            },
        )
        results = partners_from_json(answer)
        if len(wanted.split()) > 1:
            # Keep the wider list when nothing matches, rather than show nothing.
            return resolve_partner(results, wanted) or results
        return results

    # ------------------------------------------------------------------ booking
    def _person(self, id_crm: int, offer_id: int) -> dict[str, Any]:
        """One line of the booking payload.

        ``invite``, ``email`` and ``nomJoueurSaisi`` belong to the outsider path,
        where a non-member is named by hand and somebody pays for them. We never
        take it, so they stay empty and ``ticketPayant`` stays false.
        """
        return {
            "idCrm": int(id_crm),
            "idAdhesion": int(offer_id),
            "email": None,
            "invite": False,
            "ticketPayant": False,
            "nomJoueurSaisi": None,
        }

    async def async_book(self, slot: Slot, partner: Partner | None = None) -> str:
        """Book a free slot, on a subscription and for nothing.

        A slot the club wants two players on needs ``partner``: a club member,
        who brings their own subscription. Should either player have no free
        offer, we stop rather than spend a ticket or open a payment.
        """
        if not slot.creneau_id:
            raise TenupBookingError("Ce créneau n'a pas d'identifiant réservable")

        mine = await self.async_eligibility(slot)
        required = mine.required_players
        if required > 1 and partner is None:
            raise TenupBookingError(
                f"Ce créneau demande {required} joueurs; indiquez un partenaire"
            )

        me = await self.async_me()
        if me is None:
            raise TenupBookingError("Ten'Up n'a pas dit qui nous sommes")
        people = [self._person(me, self._free_offer(mine, "vous").id)]

        if required > 1 and partner is not None:
            theirs = await self.async_eligibility(slot, partner.id_crm)
            people.append(
                self._person(partner.id_crm, self._free_offer(theirs, partner.name).id)
            )

        answer = await self._api(
            "POST",
            "/clubs/reservations/paiement",
            payload={
                "codeClub": self._club_code,
                "idCreneau": int(slot.creneau_id),
                "date": slot.start.date().isoformat(),
                "heureDebut": slot.hhmmss,
                "heureFin": slot.end_hhmmss,
                "montant": 0,
                "reserverCreneauSuivant": False,
                "updateInfosPerso": False,
                "urlRetour": (
                    f"{BASE_URL}/paiement/confirmation/club-reservation"
                    f"?codeClub={self._club_code}"
                ),
                "personnes": people,
            },
        )
        if isinstance(answer, dict):
            if answer.get("errorMessage"):
                raise TenupBookingError(str(answer["errorMessage"]))
            if answer.get("idReservation"):
                slot.reservation_id = str(answer["idReservation"])
        return "Votre réservation est confirmée."

    @staticmethod
    def _free_offer(eligibility: Eligibility, who: str) -> Any:
        """The subscription of one player, or a refusal naming them.

        This is the guard that keeps a booking free: the ticket book and the
        single ticket are offers like any other in the answer, and picking one
        would spend the user's money without them asking.
        """
        offer = eligibility.free_offer
        if offer is None:
            refused = next(
                (o.error for o in eligibility.offers if o.error), None
            )
            raise TenupBookingError(
                f"Aucune formule gratuite pour {who}"
                + (f" : {refused}" if refused else "")
            )
        return offer

    async def async_cancel(self, slot: Slot) -> None:
        """Cancel one of our own reservations."""
        if not slot.reservation_id:
            raise TenupBookingError("Ce créneau n'a pas de réservation à annuler")
        await self._api("DELETE", f"/reservations/{slot.reservation_id}")
