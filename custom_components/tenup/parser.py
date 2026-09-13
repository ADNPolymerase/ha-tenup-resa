"""HTML parsing for the Ten'Up member area (Drupal pages)."""

from __future__ import annotations

import json
import unicodedata
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from typing import Any

from .const import SLOT_BUSY, SLOT_FREE, SLOT_MINE

CELL_CLASS = "adherent-reservation-calendrier-row"
HEAD_CLASS = "adherent-reservation-calendrier-row-head"
COL_CLASS = "adherent-reservation-calendrier-col"
DISABLED_CLASS = "adherent-reservation-calendrier-row-disabled"
MINE_CLASS = "adherent-reservation-calendrier-row-mine"
HALF_HOUR_CLASS = "adherent-reservation-calendrier-row-30"

BOOK_PATH_MARKER = "/reservation_court_add/"
CANCEL_PATH_MARKER = "/reservation_court_delete/"
SETTINGS_MARKER = "jQuery.extend(Drupal.settings,"

_CELL_ID_RE = re.compile(r"^(\d+)_(\d{2})(\d{2})$")
_CANCEL_RE = re.compile(r"/reservation_court_delete/nojs/(\d+)/(\d+)/(\d+)/(\d{4})")
_BOOK_RE = re.compile(r"/reservation_court_add/nojs/(\d+)/(\d+)/(\d+)/(\d+)")
_INT_RE = re.compile(r"\d+")


class TenupParseError(Exception):
    """Raised when a page does not look like what we expect."""


@dataclass(slots=True)
class Court:
    """A court of the club."""

    id: str
    name: str


@dataclass(slots=True)
class Slot:
    """One cell of the reservation grid."""

    court_id: str
    court_name: str
    start: datetime
    end: datetime
    state: str
    label: str | None = None
    book_path: str | None = None
    cancel_path: str | None = None
    reservation_id: str | None = None
    slot_id: str | None = None
    creneau_id: str | None = None
    required_players: int | None = None

    @property
    def hhmm(self) -> str:
        """Start time as HHMM, the key Ten'Up uses in cell ids and cancel URLs."""
        return self.start.strftime("%H%M")

    def mark_mine(self) -> None:
        """Ten'Up accepted a booking for this slot: show it as ours right away.

        The reservation id only comes back with the next planning fetch, so the
        cancel service falls back to court_id + start until then.
        """
        self.state = SLOT_MINE
        self.book_path = None

    def mark_free(self) -> None:
        """Ten'Up accepted a cancellation: free the cell right away."""
        self.state = SLOT_FREE
        self.label = None
        self.reservation_id = None
        self.cancel_path = None

    def as_dict(self) -> dict[str, Any]:
        """Serializable form (for the websocket command and diagnostics)."""
        return {
            "court_id": self.court_id,
            "court_name": self.court_name,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "state": self.state,
            "label": self.label,
            "reservation_id": self.reservation_id,
            "required_players": self.required_players,
        }


@dataclass(slots=True)
class Planning:
    """The reservation grid of one day."""

    day: date
    courts: list[Court] = field(default_factory=list)
    slots: list[Slot] = field(default_factory=list)
    logged_in: bool = False
    window_start: datetime | None = None
    window_end: datetime | None = None

    @property
    def free_slots(self) -> list[Slot]:
        return [s for s in self.slots if s.state == SLOT_FREE]

    @property
    def my_slots(self) -> list[Slot]:
        return [s for s in self.slots if s.state == SLOT_MINE]

    def find(self, court_id: str, start: datetime) -> Slot | None:
        for slot in self.slots:
            if slot.court_id == str(court_id) and slot.start == start:
                return slot
        return None


def _classes(attrs: dict[str, str | None]) -> set[str]:
    return set((attrs.get("class") or "").split())


class _PlanningHTMLParser(HTMLParser):
    """Stream the grid out of the Drupal page without a DOM library."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.body_classes: set[str] = set()
        self.columns: list[dict[str, Any]] = []
        self.cells: list[dict[str, Any]] = []
        self._depth = 0
        self._col: dict[str, Any] | None = None
        self._col_depth = 0
        self._cell: dict[str, Any] | None = None
        self._cell_depth = 0
        self._head_depth = 0
        self._link: dict[str, Any] | None = None
        self._link_depth = 0

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        self._depth += 1
        attrs = dict(attrs_list)
        classes = _classes(attrs)
        if tag == "body":
            self.body_classes = classes
        if tag == "div" and COL_CLASS in classes:
            self._col = {"name": "", "depth": self._depth}
            self._col_depth = self._depth
            self.columns.append(self._col)
        if tag == "div" and HEAD_CLASS in classes and self._col is not None:
            self._head_depth = self._depth
        if tag == "div" and CELL_CLASS in classes and HEAD_CLASS not in classes:
            self._cell = {
                "id": attrs.get("id") or "",
                "classes": classes,
                "start_ts": attrs.get("data-start-ts"),
                "end_ts": attrs.get("data-end-ts"),
                "links": [],
                "text": [],
                "column": self._col,
            }
            self._cell_depth = self._depth
            self.cells.append(self._cell)
        if tag == "a" and self._cell is not None:
            self._link = {"href": attrs.get("href") or "", "classes": classes, "text": []}
            self._link_depth = self._depth
            self._cell["links"].append(self._link)

    def handle_endtag(self, tag: str) -> None:
        if self._link is not None and self._depth == self._link_depth:
            self._link = None
        if self._cell is not None and self._depth == self._cell_depth:
            self._cell = None
        if self._head_depth and self._depth == self._head_depth:
            self._head_depth = 0
        if self._col is not None and self._depth == self._col_depth:
            self._col = None
        self._depth -= 1

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._head_depth and self._col is not None:
            self._col["name"] = (self._col["name"] + " " + text).strip()
        if self._link is not None:
            self._link["text"].append(text)
        if self._cell is not None:
            self._cell["text"].append(text)


def extract_drupal_settings(html: str) -> dict[str, Any]:
    """Return the object passed to ``jQuery.extend(Drupal.settings, {...})``."""
    idx = html.find(SETTINGS_MARKER)
    if idx < 0:
        raise TenupParseError("Drupal.settings not found in page")
    start = html.find("{", idx + len(SETTINGS_MARKER))
    if start < 0:
        raise TenupParseError("Drupal.settings object not found")
    try:
        obj, _ = json.JSONDecoder().raw_decode(html, start)
    except json.JSONDecodeError as err:
        raise TenupParseError(f"Drupal.settings is not valid JSON: {err}") from err
    if not isinstance(obj, dict):
        raise TenupParseError("Drupal.settings is not an object")
    return obj


_BODY_RE = re.compile(r"<body\b[^>]*\bclass=[\"']([^\"']*)[\"']", re.IGNORECASE)


def body_classes(html: str) -> set[str]:
    """Classes of the <body> tag (Drupal puts the session state there)."""
    match = _BODY_RE.search(html)
    return set(match.group(1).split()) if match else set()


def is_logged_in(html: str) -> bool:
    """Ten'Up flags the session state in the body classes."""
    classes = body_classes(html)
    return "logged-in" in classes and "not-logged-in" not in classes


def looks_signed_out(html: str) -> bool:
    """True only for a real Drupal page that states the visitor is anonymous.

    This is the single piece of evidence that the cookie is actually dead.
    Anything else (a waiting room, a bot challenge, an error page) proves
    nothing about the session and must not cost the user a new cookie.
    """
    return "not-logged-in" in body_classes(html)


_QUEUE_MARKERS = ("queue-it.net", "queueit", "queue-it")
_BOT_MARKERS = ("captcha-delivery.com", "datadome", "geo.captcha")


def interstitial_reason(html: str, final_url: str = "") -> str:
    """Name the wall Ten'Up put in front of the page, for the log message.

    Only ever used once the page is known not to be the signed-in planning and
    not a signed-out Drupal page, so a marker matched here cannot mask a real
    logout. Interstitials are small and announce themselves early, hence the
    slice.
    """
    haystack = f"{final_url}\n{html[:4000]}".lower()
    if any(marker in haystack for marker in _QUEUE_MARKERS):
        return "the Queue-it waiting room"
    if any(marker in haystack for marker in _BOT_MARKERS):
        return "a bot challenge"
    if not _BODY_RE.search(html):
        return "a page carrying no Drupal session marker"
    return "an unexpected page"


def parse_planning(html: str, day: date, tzinfo: Any) -> Planning:
    """Parse ``/club/{code}/reservations/{YYYYMMDD}``."""
    parser = _PlanningHTMLParser()
    parser.feed(html)
    planning = Planning(day=day)
    planning.logged_in = is_logged_in(html)

    try:
        settings = extract_drupal_settings(html)
        conf = settings.get("adherentReservation") or {}
        if conf.get("date_debut"):
            planning.window_start = datetime.fromtimestamp(int(conf["date_debut"]), tzinfo)
        if conf.get("date_fin"):
            planning.window_end = datetime.fromtimestamp(int(conf["date_fin"]), tzinfo)
    except TenupParseError:
        pass

    court_names: dict[str, str] = {}
    seen_courts: list[str] = []
    for cell in parser.cells:
        match = _CELL_ID_RE.match(cell["id"])
        if not match:
            continue
        court_id, hh, mm = match.groups()
        column = cell["column"]
        if column is not None and column["name"] and court_id not in court_names:
            court_names[court_id] = column["name"]
        if court_id not in seen_courts:
            seen_courts.append(court_id)

        start = datetime.combine(day, datetime.min.time(), tzinfo).replace(
            hour=int(hh), minute=int(mm)
        )
        end = _cell_end(cell, start)
        classes = cell["classes"]
        text = " ".join(cell["text"]).strip()

        slot = Slot(
            court_id=court_id,
            court_name=court_names.get(court_id, court_id),
            start=start,
            end=end,
            state=SLOT_BUSY,
            slot_id=cell["id"],
        )
        if MINE_CLASS in classes:
            slot.state = SLOT_MINE
            slot.label = cell["text"][0].strip() if cell["text"] else None
            for link in cell["links"]:
                if CANCEL_PATH_MARKER in link["href"]:
                    slot.cancel_path = link["href"]
                    cancel = _CANCEL_RE.search(link["href"])
                    if cancel:
                        slot.reservation_id = cancel.group(2)
        elif DISABLED_CLASS in classes:
            slot.state = SLOT_BUSY
            slot.label = text or None
        else:
            book = next((l for l in cell["links"] if BOOK_PATH_MARKER in l["href"]), None)
            if book is not None:
                slot.state = SLOT_FREE
                slot.book_path = book["href"]
                parsed = parse_book_path(book["href"])
                if parsed:
                    slot.creneau_id = parsed[1]
            else:
                slot.state = SLOT_BUSY
                slot.label = text or None
        planning.slots.append(slot)

    planning.courts = [Court(id=c, name=court_names.get(c, c)) for c in seen_courts]
    # Fill in names discovered after the first cell of a column.
    for slot in planning.slots:
        slot.court_name = court_names.get(slot.court_id, slot.court_id)
    return planning


_DURATION_RE = re.compile(r"^adherent-reservation-calendrier-row-(\d+)$")


def _cell_end(cell: dict[str, Any], start: datetime) -> datetime:
    # The row-30 / row-60 / row-90 class is exact; data-end-ts only has hour precision.
    for cls in cell["classes"]:
        match = _DURATION_RE.match(cls)
        if match:
            return start + timedelta(minutes=int(match.group(1)))
    end_ts = cell.get("end_ts")
    if end_ts:
        try:
            value = float(end_ts)
            hours = int(value)
            minutes = int(round((value - hours) * 60))
            return start.replace(hour=hours % 24, minute=minutes) + (
                timedelta(days=1) if hours >= 24 else timedelta()
            )
        except ValueError:
            pass
    if HALF_HOUR_CLASS in cell["classes"]:
        return start + timedelta(minutes=30)
    return start + timedelta(hours=1)


@dataclass(slots=True)
class BookingForm:
    """What ``/club/reservations/detail`` needs to be posted back."""

    player_name: str
    formula_id: str
    submit_data: str
    required_players: int
    partner_fields: list[str]
    submit_name: str = "reservation_detail_submit"
    submit_value: str = "Suivant"
    # A 2-player slot: the autocomplete key ("Prenom NOM (idAdherent)") and the
    # formula formule/ajax returned for that partner.
    partner_choice: str | None = None
    partner_formula: str | None = None

    def as_post_data(self) -> dict[str, str]:
        data = {
            "joueur1_nom": self.player_name,
            "joueur1_formule": self.formula_id,
            "submit_data": self.submit_data,
            self.submit_name: self.submit_value,
        }
        if self.partner_choice:
            data["joueur2_nom"] = self.partner_choice
        if self.partner_formula:
            data["joueur2_formule"] = self.partner_formula
        return data


def parse_partner_results(text: str) -> list[tuple[str, str]]:
    """Read the partner autocomplete: [(choice, display), ...].

    Ten'Up answers {key: display} where the KEY is what the field submits and
    carries the Ten'Up member id, so it is the half that tells two homonyms apart.
    """
    try:
        data = json.loads(text)
    except ValueError as err:
        raise TenupParseError("partner autocomplete did not answer JSON") from err
    if not isinstance(data, dict):
        raise TenupParseError("partner autocomplete did not answer an object")
    return [(str(k), str(v)) for k, v in data.items()]


def parse_formules_response(text: str) -> list[dict[str, Any]]:
    """Read the formula list from formule/ajax.

    On success the endpoint answers a JSON *string* that itself contains JSON,
    so it has to be decoded twice; an error answers a plain object instead.
    """
    try:
        data = json.loads(text)
    except ValueError as err:
        raise TenupParseError("formule/ajax did not answer JSON") from err
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError as err:
            raise TenupParseError("formule/ajax answered a string that is not JSON") from err
    if not isinstance(data, dict):
        raise TenupParseError("formule/ajax did not answer an object")
    if data.get("erreur"):
        raise TenupParseError(str(data["erreur"]))
    return [f for f in (data.get("formules") or []) if isinstance(f, dict)]


_PARTNER_CHOICE_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<ident>\d+)\)\s*$")


def _fold(text: str) -> str:
    """Case and accent insensitive form, so DOE matches Doe."""
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c)
    )
    return stripped.casefold()


def resolve_partner(
    results: list[tuple[str, str]], wanted: str
) -> list[tuple[str, str]]:
    """Narrow autocomplete results to those matching a stored friend.

    A stored entry may already be an exact choice carrying the Ten'Up member id
    ("John DOE (111111111)"), or just a name someone typed by hand
    ("DOE"). Return every candidate: the caller books when exactly one is
    left and asks the user when several are, so a father and his son are never
    confused silently.
    """
    target = _fold(wanted.strip())
    if not target:
        return []
    exact = [r for r in results if _fold(r[0]) == target]
    if exact:
        return exact
    words = [w for w in re.split(r"[^0-9a-z]+", target) if w]
    if not words:
        return []
    out = []
    for choice, display in results:
        haystack = re.split(r"[^0-9a-z]+", _fold(display))
        # Prefix, not whole word: Ten'Up answers "Do" for DOE, so a
        # truncated or half-typed name must not be thrown away here.
        if all(any(h.startswith(w) for h in haystack) for w in words):
            out.append((choice, display))
    return out


def partner_search_term(stored: str) -> str:
    """What to type into the autocomplete for a stored friend.

    A stored entry may be a full choice ("John DOE (111111111)") or a bare
    name. Ten'Up wants at least 3 characters and matches on the name, so send
    the longest word rather than the whole string.
    """
    name = stored.strip()
    parsed = _PARTNER_CHOICE_RE.match(name)
    if parsed is not None:
        name = parsed.group("name").strip()
    words = [w for w in re.split(r"\s+", name) if len(w) >= 3]
    return max(words, key=len) if words else name


def free_formulas(formulas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop anything that would charge money.

    Ten'Up already hides the paid option for a club member, but the guard is in
    code and not merely in the UI: a partner formula must never cost the user
    anything without them asking for it.
    """
    out = []
    for formula in formulas:
        if not isinstance(formula, dict) or formula.get("disabled"):
            continue
        try:
            price = float(formula.get("prix") or 0)
        except (TypeError, ValueError):
            continue
        if price > 0:
            continue
        if "UNITAIRE" in str(formula.get("value", "")).upper():
            continue
        out.append(formula)
    return out


def parse_booking_form(html: str) -> BookingForm:
    """Read the Vue form schema embedded in the reservation detail page."""
    settings = extract_drupal_settings(html)
    try:
        fields = settings["reservation_detail"]["form"]["fields"]
    except (KeyError, TypeError) as err:
        raise TenupParseError("reservation_detail form schema not found") from err

    player_group = fields.get("joueur1", {}).get("fields", {})
    name_field = player_group.get("joueur1_nom", {}).get("field_data", {})
    formula_field = player_group.get("joueur1_formule", {}).get("field_data", {})
    formula_value = formula_field.get("value")
    if isinstance(formula_value, dict):
        formula_value = formula_value.get("value")
    submit_data = fields.get("submit_data", {}).get("field_data", {}).get("value")
    submit = fields.get("submit", {}).get("field_data", {})

    if not submit_data or formula_value is None:
        raise TenupParseError("booking form is incomplete (submit_data or formula missing)")

    players_text = fields.get("nombre_joueur_obligatoire", {}).get("field_data", {}).get("value", "")
    numbers = _INT_RE.findall(str(players_text))
    required_players = int(numbers[0]) if numbers else 1

    partner_fields = list((fields.get("group_partenaires", {}).get("fields") or {}).keys())

    return BookingForm(
        player_name=str(name_field.get("value") or ""),
        formula_id=str(formula_value),
        submit_data=str(submit_data),
        required_players=required_players,
        partner_fields=partner_fields,
        submit_name=str(submit.get("name") or "reservation_detail_submit"),
        submit_value=str(submit.get("value") or "Suivant"),
    )


class _MessagesParser(HTMLParser):
    """Collect the text of Drupal ``.messages`` blocks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.messages: list[str] = []
        self._depth = 0
        self._in: int = 0
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        self._depth += 1
        if self._in:
            return
        classes = _classes(dict(attrs_list))
        if tag == "div" and "messages" in classes:
            self._in = self._depth
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if self._in and self._depth == self._in:
            text = " ".join(self._buf).strip()
            if text:
                self.messages.append(text)
            self._in = 0
        self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in:
            text = data.strip()
            if text and text != "×":
                self._buf.append(text)


def parse_messages(html: str) -> list[str]:
    """Return Drupal status/error messages shown on a page."""
    parser = _MessagesParser()
    parser.feed(html)
    cleaned = []
    for message in parser.messages:
        message = re.sub(r"^(Message d'erreur|Message de statut|Message d'avertissement)\s*", "", message)
        cleaned.append(message.strip())
    return cleaned


def parse_book_path(path: str) -> tuple[str, str, int, int] | None:
    """court_id, slot_param_id, start_epoch, end_epoch from a booking link."""
    match = _BOOK_RE.search(path)
    if not match:
        return None
    court_id, param_id, start, end = match.groups()
    return court_id, param_id, int(start), int(end)
