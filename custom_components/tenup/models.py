"""The shapes Ten'Up hands back, and how a day of courts is read from them.

Ten'Up serves its member area as a JSON API: a day of the club's grid, the
offers a player may take a slot with, and the player's own reservations. The
dataclasses here are the only form the rest of the integration knows, so a
change of wording upstream stops at this file.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any

from .const import OFFER_SUBSCRIPTION, SLOT_BUSY, SLOT_FREE, SLOT_MINE


class TenupParseError(Exception):
    """Ten'Up answered JSON that does not hold what we asked for."""


def _as_time(raw: Any) -> time:
    """``"20:00:00"`` -> ``time(20, 0)``; Ten'Up always sends seconds."""
    try:
        hour, minute, *rest = str(raw).split(":")
        return time(int(hour), int(minute), int(rest[0]) if rest else 0)
    except (AttributeError, IndexError, TypeError, ValueError) as err:
        raise TenupParseError(f"not a time: {raw!r}") from err


def _as_date(raw: Any) -> date:
    """``"2026-10-16"`` -> a date."""
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError) as err:
        raise TenupParseError(f"not a date: {raw!r}") from err


@dataclass(slots=True)
class Court:
    """A court of the club."""

    id: str
    name: str
    covered: bool = False
    lit: bool = False
    surface: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "covered": self.covered,
            "lit": self.lit,
            "surface": self.surface,
        }


@dataclass(slots=True)
class Offer:
    """One way a given player may take a given slot.

    ``id`` is what the booking payload calls ``idAdhesion``. Every player in a
    booking brings their own, so two players on the same court can hold two
    different offers.
    """

    id: int
    kind: str
    label: str
    required_players: int = 1
    eligible: bool = True
    error: str | None = None
    tickets_left: int | None = None

    @property
    def free(self) -> bool:
        """True only for a subscription, the one offer that costs nothing.

        A ticket book debits a ticket and a single ticket is bought online, so
        neither may ever be picked on the user's behalf. Price is no help here:
        Ten'Up reports the club's ticket rate on the subscription too.
        """
        return self.kind == OFFER_SUBSCRIPTION

    @property
    def usable(self) -> bool:
        return self.eligible and self.free


@dataclass(slots=True)
class Eligibility:
    """What Ten'Up allows one player to do on one slot."""

    offers: list[Offer] = field(default_factory=list)
    id_crm: int | None = None
    extra_players_allowed: bool = False
    outsiders_allowed: bool = False
    recent_partners: list[Partner] = field(default_factory=list)

    @property
    def required_players(self) -> int:
        """How many players the club wants, as the offers report it."""
        return max((offer.required_players for offer in self.offers), default=1)

    @property
    def free_offer(self) -> Offer | None:
        """The subscription to book with, or None when there is none to use."""
        return next((offer for offer in self.offers if offer.usable), None)


@dataclass(slots=True)
class Partner:
    """A club member who may be named as a second player."""

    id_crm: int
    last_name: str
    first_name: str

    @property
    def name(self) -> str:
        return " ".join(part for part in (self.first_name, self.last_name) if part)

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id_crm, "name": self.name}


@dataclass(slots=True)
class Slot:
    """One cell of the reservation grid."""

    court_id: str
    court_name: str
    start: datetime
    end: datetime
    state: str
    label: str | None = None
    reservation_id: str | None = None
    creneau_id: str | None = None
    required_players: int | None = None
    cancellable: bool = False

    @property
    def hhmmss(self) -> str:
        """Start time the way the API takes it in a booking."""
        return self.start.strftime("%H:%M:%S")

    @property
    def end_hhmmss(self) -> str:
        return self.end.strftime("%H:%M:%S")

    def mark_mine(self, reservation_id: str | None = None) -> None:
        """Ten'Up accepted a booking: show the cell as ours without waiting."""
        self.state = SLOT_MINE
        self.cancellable = True
        if reservation_id:
            self.reservation_id = reservation_id

    def mark_free(self) -> None:
        """Ten'Up accepted a cancellation: free the cell without waiting."""
        self.state = SLOT_FREE
        self.label = None
        self.reservation_id = None
        self.cancellable = False

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
    window_end: date | None = None

    @property
    def free_slots(self) -> list[Slot]:
        return [slot for slot in self.slots if slot.state == SLOT_FREE]

    @property
    def my_slots(self) -> list[Slot]:
        return [slot for slot in self.slots if slot.state == SLOT_MINE]

    def find(self, court_id: str, start: datetime) -> Slot | None:
        for slot in self.slots:
            if slot.court_id == str(court_id) and slot.start == start:
                return slot
        return None


def _reservation_label(reservation: dict[str, Any]) -> str | None:
    """What to show on a taken cell: the club's own wording, else the players."""
    label = (reservation.get("libelle") or "").strip()
    if label:
        return label
    names = [
        " ".join(
            part
            for part in (
                str(player.get("prenom") or "").strip(),
                str(player.get("nom") or "").strip(),
            )
            if part
        )
        for player in reservation.get("joueurs") or []
    ]
    names = [name for name in names if name]
    return ", ".join(names) or None


def _is_mine(reservation: dict[str, Any], me: int | None) -> bool:
    """Ten'Up names the players; we are the one whose idCrm is the profile's.

    The profile calls it ``id`` and the grid calls it ``idCrm``: they are the
    same number, which is the only link between a reservation and its owner.
    """
    if me is None:
        return False
    return any(
        str(player.get("idCrm")) == str(me) for player in reservation.get("joueurs") or []
    )


def planning_from_json(
    payload: Any, day: date, tzinfo: Any, me: int | None = None
) -> Planning:
    """Read ``GET /clubs/reservations?date=&codeClub=`` into a day of slots."""
    if not isinstance(payload, dict):
        raise TenupParseError("the planning is not an object")
    raw_courts = payload.get("courts")
    if not isinstance(raw_courts, list):
        raise TenupParseError("the planning carries no courts")

    planning = Planning(day=day)
    if payload.get("dateFin"):
        planning.window_end = _as_date(payload["dateFin"])

    for raw_court in raw_courts:
        if not isinstance(raw_court, dict):
            continue
        court_id = str(raw_court.get("id") or "")
        if not court_id:
            continue
        surface = raw_court.get("surface") or {}
        court = Court(
            id=court_id,
            name=str(raw_court.get("nom") or court_id),
            covered=bool(raw_court.get("couvert")),
            lit=bool(raw_court.get("eclaire")),
            surface=(surface.get("libelle") if isinstance(surface, dict) else None),
        )
        planning.courts.append(court)

        for raw_slot in raw_court.get("creneaux") or []:
            if not isinstance(raw_slot, dict):
                continue
            start = datetime.combine(day, _as_time(raw_slot.get("heureDebut")), tzinfo)
            end = datetime.combine(day, _as_time(raw_slot.get("heureFin")), tzinfo)
            if end <= start:
                # A slot that ends past midnight is the only way this happens.
                end = end.replace(day=end.day) if end.day != start.day else end
            reservation = raw_slot.get("reservation")
            if isinstance(reservation, dict):
                mine = _is_mine(reservation, me)
                planning.slots.append(
                    Slot(
                        court_id=court.id,
                        court_name=court.name,
                        start=start,
                        end=end,
                        state=SLOT_MINE if mine else SLOT_BUSY,
                        label=_reservation_label(reservation),
                        reservation_id=(
                            str(reservation["id"]) if reservation.get("id") else None
                        ),
                        creneau_id=(
                            str(raw_slot["id"]) if raw_slot.get("id") else None
                        ),
                        cancellable=bool(reservation.get("annulable")) and mine,
                    )
                )
                continue
            if not raw_slot.get("reservable"):
                # Closed, out of the booking window, or kept by the club.
                continue
            planning.slots.append(
                Slot(
                    court_id=court.id,
                    court_name=court.name,
                    start=start,
                    end=end,
                    state=SLOT_FREE,
                    creneau_id=str(raw_slot["id"]) if raw_slot.get("id") else None,
                )
            )
    return planning


def eligibility_from_json(payload: Any) -> Eligibility:
    """Read ``POST /clubs/reservations/eligibilite`` for one player."""
    if not isinstance(payload, dict):
        raise TenupParseError("the eligibility is not an object")
    player = payload.get("joueur")
    player = player if isinstance(player, dict) else {}
    offers: list[Offer] = []
    for raw in player.get("offres") or []:
        if not isinstance(raw, dict) or raw.get("id") is None:
            continue
        offers.append(
            Offer(
                id=int(raw["id"]),
                kind=str(raw.get("type") or ""),
                label=str(raw.get("libelle") or ""),
                required_players=int(raw.get("nombreJoueursObligatoires") or 1),
                eligible=bool(raw.get("eligible", True)),
                error=raw.get("erreur") or None,
                tickets_left=raw.get("ticketsRestant"),
            )
        )
    return Eligibility(
        offers=offers,
        id_crm=player.get("idCrm"),
        extra_players_allowed=bool(payload.get("joueursSupplementairesAutorises")),
        outsiders_allowed=bool(payload.get("joueursExternesAutorises")),
        recent_partners=partners_from_json(payload.get("partenairesRecents")),
    )


def partners_from_json(payload: Any) -> list[Partner]:
    """Read a list of club members, from the search or from recent partners."""
    rows = payload.get("hits") if isinstance(payload, dict) else payload
    partners: list[Partner] = []
    for raw in rows or []:
        if not isinstance(raw, dict) or raw.get("idCrm") is None:
            continue
        partners.append(
            Partner(
                id_crm=int(raw["idCrm"]),
                last_name=str(raw.get("nom") or "").strip(),
                first_name=str(raw.get("prenom") or "").strip(),
            )
        )
    return partners


def normalise(text: str) -> str:
    """Casefolded, accent-free, single-spaced: how names are compared."""
    stripped = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    return " ".join(stripped.casefold().split())


def partner_search_term(wanted: str) -> str:
    """Ten'Up searches one word at a time, so send the longest one.

    "Jean Dupont" returns nothing; "Dupont" returns every Dupont, which the
    caller then narrows with everything that was typed.
    """
    words = [word for word in normalise(wanted).split() if word]
    if not words:
        return wanted.strip()
    return max(words, key=len)


def resolve_partner(partners: list[Partner], wanted: str) -> list[Partner]:
    """Keep the members that match every word the user typed."""
    words = [word for word in normalise(wanted).split() if word]
    if not words:
        return []
    return [
        partner
        for partner in partners
        if all(word in normalise(partner.name) for word in words)
    ]


# How a partner travels between the card and the booking: the display name with
# the member id in brackets. The name alone cannot tell two homonyms apart, and
# a father and his son share a surname often enough for that to matter.
_CHOICE_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<ident>\d+)\)\s*$")


def partner_choice(partner: Partner) -> str:
    """What the card stores for a friend, and sends back to book with them."""
    return f"{partner.name} ({partner.id_crm})"


def parse_partner_choice(label: str) -> Partner | None:
    """Read back what :func:`partner_choice` wrote, or None for a bare name."""
    match = _CHOICE_RE.match(label.strip())
    if match is None:
        return None
    name = match.group("name").strip()
    first, _, last = name.partition(" ")
    return Partner(
        id_crm=int(match.group("ident")),
        last_name=last.strip() or first,
        first_name=first if last.strip() else "",
    )
