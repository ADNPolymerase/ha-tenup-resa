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
    interstitial_reason,
    is_logged_in,
    looks_signed_out,
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


PARTNER_AUTOCOMPLETE_PATH = "/adherent/autocomplete/partenaire"
# What RechercheJoueurAutocomplete actually calls: it ignores the
# autocomplete_path the page advertises and hardcodes this one.
JOUEUR_AUTOCOMPLETE_PATH = "/club/autocomplete/partenaire"
_PROBE_SAMPLE = 400
_JS_RADIUS = 320
_JS_NEEDLES = (
    "autocomplete/partenaire",
    "params_formule_joueur_ajax",
    "formule/ajax",
    "formuleAjax",
    "joueur2_nom",
    "idPartenaire",
    "detail/submit",
)
_MAX_JS_ASSETS = 25
_SCRIPT_SRC_RE = re.compile(r'<script[^>]+src="([^"]+)"', re.I)


def _json_sample(value: Any, limit: int) -> str:
    """Serialise a page structure for the probe report, bounded."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)[:limit]


def partner_autocomplete_candidates(
    query: str, path: str = PARTNER_AUTOCOMPLETE_PATH
) -> list[str]:
    """Where the partner autocomplete really lives, page claims notwithstanding.

    The page advertises autocomplete_path on joueur2_nom, but the component that
    consumes it (RechercheJoueurAutocomplete) ignores the prop and calls
    /club/autocomplete/partenaire/<term>. The advertised path is kept as a
    fallback in case another club or a later build honours it.
    """
    q = quote(query.strip(), safe="")
    if not q:
        raise ValueError("empty query")
    advertised = ("/" + path.lstrip("/")).rstrip("/")
    out: list[str] = []
    for candidate in (
        f"{JOUEUR_AUTOCOMPLETE_PATH}/{q}",
        f"{JOUEUR_AUTOCOMPLETE_PATH}/{q}?term={q}",
        f"/club/reservations{advertised}/{q}",
        f"{advertised}/{q}",
    ):
        if candidate not in out:
            out.append(candidate)
    return out


def formule_ajax_candidates(book_path: str, url_fragment: str) -> list[str]:
    """``params_formule_joueur_ajax.url`` is relative and Ten'Up never says to what."""
    frag = (url_fragment or "").strip("/")
    if not frag:
        return []
    bases = ["/club/reservations/", "/club/", "/"]
    if book_path:
        bases.append(urljoin(book_path if book_path.startswith("/") else "/" + book_path, "./"))
    out: list[str] = []
    for base in bases:
        candidate = urljoin(base, frag)
        if candidate not in out:
            out.append(candidate)
    return out


_PARTNER_CHOICE_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<ident>\d+)\)\s*$")


def parse_partner_choice(label: str) -> tuple[str, str] | None:
    """Split an autocomplete key: 'John DOE (111111111)' -> name + licence id.

    The autocomplete answers {key: display}, and the key is what the field
    submits, so it carries the identifier that tells two homonyms apart.
    """
    match = _PARTNER_CHOICE_RE.match(label.strip())
    if match is None:
        return None
    return match.group("name").strip(), match.group("ident")


def partner_post_variants(base: dict[str, str], label: str) -> list[dict[str, str]]:
    """formule/ajax needs the partner, and Ten'Up never says under which key."""
    parsed = parse_partner_choice(label)
    if parsed is None:
        return []
    _name, ident = parsed
    out: list[dict[str, str]] = []
    for extra in (
        {"joueur2_nom": label},
        {"idPartenaire": ident},
        {"idJoueur": ident},
        {"idAdherent": ident},
        {"joueur2_nom": label, "idPartenaire": ident},
    ):
        payload = dict(base)
        payload.update(extra)
        out.append(payload)
    return out


def script_urls(html: str, limit: int = _MAX_JS_ASSETS) -> list[str]:
    """The page's own JS bundles, absolute.

    Their source is the only place that states how autocomplete_path is turned
    into a real request. The public copies sit behind the waiting room, but a
    signed-in session fetches them normally.
    """
    out: list[str] = []
    for src in _SCRIPT_SRC_RE.findall(html):
        if ".js" not in src:
            continue
        url = src if src.startswith("http") else urljoin(BASE_URL, src)
        if url not in out:
            out.append(url)
    return out[:limit]


def find_snippets(
    text: str, needle: str, radius: int = _JS_RADIUS, limit: int = 3
) -> list[str]:
    """Bounded context around each occurrence, so a multi-MB bundle stays readable."""
    out: list[str] = []
    start = 0
    while len(out) < limit:
        i = text.find(needle, start)
        if i < 0:
            break
        out.append(" ".join(text[max(0, i - radius) : i + radius + len(needle)].split()))
        start = i + len(needle)
    return out


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

    async def async_probe_partner(
        self, book_path: str, query: str, partner: str | None = None
    ) -> dict[str, Any]:
        """Read-only reconnaissance of the 2-player flow. Never books anything.

        Ten'Up serves its JavaScript from behind the waiting room, so the request
        shapes of the partner autocomplete and of ``formule/ajax`` cannot be read
        anywhere but from a signed-in session.
        """
        body, _ = await self._get_html(book_path)
        settings = extract_drupal_settings(body)
        detail = settings.get("reservation_detail") or {}
        params = detail.get("params_formule_joueur_ajax") or {}
        cotisation = detail.get("cotisation") or {}
        fields = (detail.get("form") or {}).get("fields") or {}

        def _sample(text: str) -> str:
            return " ".join(text.split())[:_PROBE_SAMPLE]

        # The joueur2 block is what we actually need to reproduce; dump it whole.
        joueur2: dict[str, Any] = {}
        for cot in cotisation.values():
            candidate = (cot or {}).get("joueur2") or {}
            if candidate:
                joueur2 = candidate
                break
        nom_field = (joueur2.get("fields") or {}).get("joueur2_nom") or {}
        auto_path = nom_field.get("autocomplete_path") or PARTNER_AUTOCOMPLETE_PATH

        report: dict[str, Any] = {
            "book_path": book_path,
            "required_players": fields.get("nombre_joueur_obligatoire"),
            "statut_invitation": fields.get("statut_invitation"),
            "autocomplete_path_from_page": auto_path,
            "joueur2_spec": _json_sample(joueur2, 2500),
            "ajax_params": {k: v for k, v in params.items() if k != "url"},
            "ajax_url_fragment": params.get("url"),
            "ticket_restants": detail.get("ticketRestants"),
            "paiement_en_ligne": detail.get("paiementEnLigneAutorise"),
            "autocomplete": [],
            "formule_ajax": [],
        }

        for url in partner_autocomplete_candidates(query, auto_path):
            try:
                text, final, status = await self._request(
                    "GET", f"{BASE_URL}{url}", headers=_JSON_HEADERS
                )
            except TenupError as err:
                report["autocomplete"].append({"url": url, "error": str(err)})
                continue
            report["autocomplete"].append(
                {"url": url, "status": status, "final_path": final.path,
                 "body": " ".join(text.split())[:900]}
            )

        post_data = {k: str(v) for k, v in params.items() if k != "url" and v is not None}
        query_string = urlencode(post_data)
        for url in formule_ajax_candidates(book_path, params.get("url", "")):
            target = f"{BASE_URL}{url}?{query_string}" if query_string else f"{BASE_URL}{url}"
            try:
                text, final, status = await self._request(
                    "GET", target, headers=_JSON_HEADERS
                )
            except TenupError as err:
                report["formule_ajax"].append({"url": url, "method": "GET", "error": str(err)})
                continue
            report["formule_ajax"].append(
                {"url": url, "method": "GET", "status": status,
                 "final_path": final.path, "body": _sample(text)}
            )
            # Only the endpoint that answers JSON is worth a POST.
            if status == 200 and text.lstrip().startswith("{"):
                try:
                    ptext, pfinal, pstatus = await self._request(
                        "POST",
                        f"{BASE_URL}{url}",
                        headers={
                            **_JSON_HEADERS,
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Origin": BASE_URL,
                            "Referer": urljoin(BASE_URL, book_path),
                            "X-Requested-With": "XMLHttpRequest",
                        },
                        data=post_data,
                    )
                except TenupError as err:
                    report["formule_ajax"].append({"url": url, "method": "POST", "error": str(err)})
                    continue
                report["formule_ajax"].append(
                    {"url": url, "method": "POST", "status": pstatus,
                     "final_path": pfinal.path, "body": _sample(ptext)}
                )
        if partner:
            report["partner_parsed"] = parse_partner_choice(partner)
            report["partner_attempts"] = []
            for payload in partner_post_variants(post_data, partner):
                added = sorted(set(payload) - set(post_data))
                try:
                    text, _, status = await self._request(
                        "POST",
                        f"{BASE_URL}/club/reservations/formule/ajax",
                        headers={
                            **_JSON_HEADERS,
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Origin": BASE_URL,
                            "Referer": urljoin(BASE_URL, book_path),
                            "X-Requested-With": "XMLHttpRequest",
                        },
                        data=payload,
                    )
                except TenupError as err:
                    report["partner_attempts"].append({"keys": added, "error": str(err)})
                    continue
                report["partner_attempts"].append(
                    {"keys": added, "status": status, "body": _sample(text)}
                )

        report["js"] = []
        report["js_scanned"] = []
        for url in script_urls(body):
            try:
                text, _, status = await self._request("GET", url, headers=_HTML_HEADERS)
            except TenupError as err:
                report["js"].append({"url": url, "error": str(err)})
                continue
            hits = {
                needle: found
                for needle in _JS_NEEDLES
                if (found := find_snippets(text, needle, limit=2))
            }
            report["js_scanned"].append(url.rsplit("/", 1)[-1][:40])
            if hits:
                report["js"].append({"url": url, "status": status, "hits": hits})
        return report

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
