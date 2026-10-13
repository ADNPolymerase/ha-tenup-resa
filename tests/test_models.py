"""Reading the JSON Ten'Up answers with.

Every name here is made up. Real members never appear in this repository, not
even as test data.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from custom_components.tenup.const import SLOT_BUSY, SLOT_FREE, SLOT_MINE
from custom_components.tenup.models import (
    Offer,
    Partner,
    TenupParseError,
    eligibility_from_json,
    parse_partner_choice,
    partner_choice,
    partner_search_term,
    partners_from_json,
    planning_from_json,
    resolve_partner,
)

TZ = timezone(timedelta(hours=2))
DAY = date(2026, 10, 16)
ME = 10000000001
SOMEONE = 10000000002


def slot(start: str, end: str, slot_id: int, *, reservable=True, reservation=None):
    return {
        "heureDebut": start,
        "heureFin": end,
        "id": slot_id,
        "reservable": reservable,
        "surcharge": None,
        "reservation": reservation,
    }


def booking(res_id, players, *, label=None, cancellable=True):
    return {
        "id": res_id,
        "libelle": label,
        "paiementEnAttente": False,
        "annulable": cancellable,
        "type": "PONC_JOUEUR",
        "joueurs": [
            {"idCrm": pid, "nom": last, "prenom": first, "invite": False}
            for pid, first, last in players
        ],
    }


PLANNING = {
    "dateFin": "2026-10-20",
    "courts": [
        {
            "id": 21099,
            "nom": "Court COUVERT",
            "couvert": True,
            "eclaire": True,
            "surface": {"code": "RES", "libelle": "Résine"},
            "pratique": {"code": "TENNIS", "libelle": "Tennis"},
            "creneaux": [
                slot("08:00:00", "09:00:00", 56087),
                slot(
                    "09:00:00",
                    "10:00:00",
                    56087,
                    reservable=False,
                    reservation=booking(
                        170000001, [(ME, "Alex", "DOE"), (SOMEONE, "Robin", "ROE")]
                    ),
                ),
                slot(
                    "10:00:00",
                    "11:00:00",
                    56087,
                    reservable=False,
                    reservation=booking(
                        170000002, [(SOMEONE, "Robin", "ROE")], cancellable=False
                    ),
                ),
                slot("11:00:00", "12:00:00", 56087, reservable=False),
            ],
        },
        {
            "id": 37195,
            "nom": "PLATRE 1",
            "couvert": False,
            "eclaire": True,
            "surface": {"code": "BP", "libelle": "Béton poreux"},
            "creneaux": [
                slot("20:00:00", "21:00:00", 56132),
                slot(
                    "21:00:00",
                    "22:00:00",
                    56132,
                    reservable=False,
                    reservation=booking(
                        170000003, [(SOMEONE, "Robin", "ROE")], label="Equipe 1"
                    ),
                ),
            ],
        },
    ],
}


def read(payload=None, me=ME):
    return planning_from_json(payload or PLANNING, DAY, TZ, me)


def test_courts_carry_what_the_card_shows():
    planning = read()
    covered, outdoor = planning.courts
    assert (covered.id, covered.name) == ("21099", "Court COUVERT")
    assert covered.covered is True and covered.lit is True
    assert covered.surface == "Résine"
    assert outdoor.covered is False


def test_a_slot_is_free_booked_or_ours():
    planning = read()
    by_key = {f"{s.court_id}_{s.hhmmss}": s for s in planning.slots}

    free = by_key["21099_08:00:00"]
    assert free.state == SLOT_FREE
    assert free.creneau_id == "56087"
    assert free.reservation_id is None

    mine = by_key["21099_09:00:00"]
    assert mine.state == SLOT_MINE
    assert mine.reservation_id == "170000001"
    assert mine.cancellable is True
    assert mine.label == "Alex DOE, Robin ROE"

    theirs = by_key["21099_10:00:00"]
    assert theirs.state == SLOT_BUSY
    assert theirs.cancellable is False, "only our own bookings may be cancelled"


def test_a_closed_slot_is_not_shown_at_all():
    """Ten'Up keeps sending the cell; a slot nobody can take is not a slot."""
    planning = read()
    assert "21099_11:00:00" not in {f"{s.court_id}_{s.hhmmss}" for s in planning.slots}


def test_a_booking_that_is_not_ours_is_never_cancellable_even_when_tenup_says_so():
    """``annulable`` answers for the club's rules, not for who we are."""
    payload = {
        "courts": [
            {
                "id": 1,
                "nom": "COURT 1",
                "creneaux": [
                    slot(
                        "08:00:00",
                        "09:00:00",
                        9,
                        reservable=False,
                        reservation=booking(
                            1, [(SOMEONE, "Robin", "ROE")], cancellable=True
                        ),
                    )
                ],
            }
        ]
    }
    (only,) = planning_from_json(payload, DAY, TZ, ME).slots
    assert only.state == SLOT_BUSY and only.cancellable is False


def test_without_knowing_who_we_are_nothing_is_ours():
    """The profile call can fail; a wrong "mine" would offer to cancel a stranger's."""
    assert read(me=None).my_slots == []


def test_the_club_label_wins_over_the_player_names():
    planning = read()
    (team,) = [s for s in planning.slots if s.reservation_id == "170000003"]
    assert team.label == "Equipe 1"


def test_the_booking_window_is_read_for_the_coordinator():
    assert read().window_end == date(2026, 10, 20)


def test_times_become_aware_datetimes_on_the_right_day():
    free = read().free_slots[0]
    assert free.start == datetime(2026, 10, 16, 8, 0, tzinfo=TZ)
    assert free.end == datetime(2026, 10, 16, 9, 0, tzinfo=TZ)


def test_find_locates_a_cell_by_court_and_start():
    planning = read()
    found = planning.find("37195", datetime(2026, 10, 16, 20, 0, tzinfo=TZ))
    assert found is not None and found.state == SLOT_FREE
    assert planning.find("37195", datetime(2026, 10, 16, 7, 0, tzinfo=TZ)) is None


def test_slot_marks_reflect_an_accepted_change():
    """Ten'Up has already accepted: the cell must change without a refetch.

    The coordinator debounces its refresh by about ten seconds and then refetches
    every day, so without this the grid keeps showing the cancelled reservation
    long enough that the card has to be reloaded by hand.
    """
    planning = read()
    by_key = {f"{s.court_id}_{s.hhmmss}": s for s in planning.slots}

    mine = by_key["21099_09:00:00"]
    mine.mark_free()
    assert mine.state == SLOT_FREE
    assert mine.label is None
    assert mine.reservation_id is None, "a freed cell must not keep a cancel target"
    assert mine.cancellable is False
    assert mine.court_id == "21099", "the cell itself does not move"

    free = by_key["37195_20:00:00"]
    free.mark_mine("170000009")
    assert free.state == SLOT_MINE
    assert free.cancellable is True
    assert free.reservation_id == "170000009"


@pytest.mark.parametrize("bad", [None, [], "planning", {"courts": "none"}])
def test_a_planning_that_is_not_one_is_refused(bad):
    with pytest.raises(TenupParseError):
        planning_from_json(bad, DAY, TZ, ME)


def test_a_slot_with_a_broken_time_is_refused():
    payload = {"courts": [{"id": 1, "nom": "C", "creneaux": [slot("huit", "09:00:00", 1)]}]}
    with pytest.raises(TenupParseError):
        planning_from_json(payload, DAY, TZ, ME)


# ----------------------------------------------------------------- eligibility
ELIGIBILITY = {
    "carnetsReservantAutorises": True,
    "ticketsAutorises": True,
    "joueursSupplementairesAutorises": False,
    "joueursExternesAutorises": True,
    "joueur": {
        "idCrm": ME,
        "offres": [
            {
                "id": 1,
                "type": "AB",
                "libelle": "Adultes 2027",
                "ticketsRestant": None,
                "eligible": True,
                "erreur": None,
                "nombreJoueursObligatoires": 2,
                "tarifTicket": 6,
                "creneauSuivant": False,
            },
            {
                "id": 2,
                "type": "CA",
                "libelle": "Tickets adhérents",
                "ticketsRestant": 5,
                "eligible": True,
                "erreur": None,
                "nombreJoueursObligatoires": 2,
                "tarifTicket": 6,
                "creneauSuivant": False,
            },
        ],
    },
    "partenairesRecents": [{"idCrm": SOMEONE, "nom": "ROE", "prenom": "Robin"}],
}


def test_eligibility_reads_the_offers_and_who_they_belong_to():
    eligibility = eligibility_from_json(ELIGIBILITY)
    assert eligibility.id_crm == ME
    assert [offer.label for offer in eligibility.offers] == [
        "Adultes 2027",
        "Tickets adhérents",
    ]
    assert eligibility.outsiders_allowed is True
    assert eligibility.extra_players_allowed is False
    assert [p.name for p in eligibility.recent_partners] == ["Robin ROE"]


def test_the_club_demands_as_many_players_as_the_offers_say():
    assert eligibility_from_json(ELIGIBILITY).required_players == 2


def test_only_a_subscription_is_free_whatever_the_quoted_rate():
    """The trap: Ten'Up quotes the club's ticket rate on the subscription too.

    Picking the ticket book would silently spend a ticket, and a single ticket
    is bought online. Neither may ever be chosen for the user, so the kind of
    offer decides, never its price.
    """
    eligibility = eligibility_from_json(ELIGIBILITY)
    subscription, tickets = eligibility.offers
    assert subscription.free is True and tickets.free is False
    assert tickets.tickets_left == 5, "a ticket book still costs a ticket"
    assert eligibility.free_offer is subscription


def test_an_offer_the_club_refuses_is_not_usable():
    refused = Offer(id=3, kind="AB", label="Adultes", eligible=False, error="Quota atteint")
    assert refused.free is True and refused.usable is False


def test_an_eligibility_without_a_free_offer_says_so():
    payload = {"joueur": {"offres": [dict(ELIGIBILITY["joueur"]["offres"][1])]}}
    assert eligibility_from_json(payload).free_offer is None


def test_an_empty_eligibility_still_answers_one_player():
    assert eligibility_from_json({}).required_players == 1


# --------------------------------------------------------------------- partners
SEARCH = {
    "total": 3,
    "hits": [
        {"idCrm": 1, "nom": "DOE", "prenom": "Alex"},
        {"idCrm": 2, "nom": "DOE", "prenom": "Charlie"},
        {"idCrm": 3, "nom": "ROE", "prenom": "Robin"},
    ],
}


def test_a_search_is_read_into_members():
    found = partners_from_json(SEARCH)
    assert [p.name for p in found] == ["Alex DOE", "Charlie DOE", "Robin ROE"]
    assert found[0].id_crm == 1


def test_a_search_survives_rows_without_an_identifier():
    assert partners_from_json({"hits": [{"nom": "DOE"}, SEARCH["hits"][0]]})[0].id_crm == 1


def test_the_search_term_is_the_one_word_tenup_answers_to():
    """Ten'Up searches a single word: a full name returns nothing at all."""
    assert partner_search_term("Alex DOE") == "alex"
    assert partner_search_term("  Robin   ROE ") == "robin"
    assert partner_search_term("Ève DÜ") == "eve", "accents are dropped, longest wins"


def test_a_surname_alone_keeps_both_homonyms():
    both = resolve_partner(partners_from_json(SEARCH), "DOE")
    assert [p.name for p in both] == ["Alex DOE", "Charlie DOE"]


def test_a_first_name_tells_homonyms_apart_whatever_the_case_and_accents():
    (one,) = resolve_partner(partners_from_json(SEARCH), "charlie doe")
    assert one.id_crm == 2
    assert resolve_partner(partners_from_json(SEARCH), "Nobody HERE") == []


def test_a_friend_travels_with_the_member_id_behind_the_name():
    """A name alone cannot tell a father from his son."""
    stored = partner_choice(Partner(id_crm=42, last_name="DOE", first_name="Alex"))
    assert stored == "Alex DOE (42)"
    back = parse_partner_choice(stored)
    assert back is not None and back.id_crm == 42 and back.name == "Alex DOE"


def test_a_bare_name_is_not_a_choice_and_must_be_searched_for():
    assert parse_partner_choice("Alex DOE") is None
