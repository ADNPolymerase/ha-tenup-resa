"""Exercise TenupClient against a fake aiohttp session.

Ten'Up answers JSON now, so what is worth pinning down is what we send it: the
right query, the right body, and above all a booking that can never cost the
user anything. Every name and member id here is invented.
"""
import asyncio
import json
from datetime import date, datetime, timedelta, timezone

import aiohttp
import pytest
from yarl import URL

from custom_components.tenup.api import (
    TenupAuthError,
    TenupBookingError,
    TenupClient,
    TenupConnectionError,
)
from custom_components.tenup.models import Partner, Slot
from custom_components.tenup.const import SLOT_FREE

TZ = timezone(timedelta(hours=2))
ME = 10000000001
FRIEND = 10000000002

PROFILE = {"id": ME, "idPersonne": 999, "nom": "DOE", "prenom": "Alex"}


def offer(offer_id, kind, players=1, eligible=True, erreur=None):
    return {
        "id": offer_id,
        "type": kind,
        "libelle": "Adultes" if kind == "AB" else "Tickets",
        "ticketsRestant": None if kind == "AB" else 5,
        "eligible": eligible,
        "erreur": erreur,
        "nombreJoueursObligatoires": players,
        "tarifTicket": 6,
    }


def eligibility(*offers, id_crm=ME):
    return {
        "joueursSupplementairesAutorises": False,
        "joueursExternesAutorises": True,
        "joueur": {"idCrm": id_crm, "offres": list(offers)},
        "partenairesRecents": [],
    }


PLANNING = {
    "dateFin": "2026-10-20",
    "courts": [
        {
            "id": 37195,
            "nom": "PLATRE 1",
            "couvert": False,
            "eclaire": True,
            "surface": {"libelle": "Béton poreux"},
            "creneaux": [
                {
                    "heureDebut": "20:00:00",
                    "heureFin": "21:00:00",
                    "id": 56132,
                    "reservable": True,
                    "surcharge": None,
                    "reservation": None,
                }
            ],
        }
    ],
}


def free_slot():
    return Slot(
        court_id="37195",
        court_name="PLATRE 1",
        start=datetime(2026, 10, 16, 20, 0, tzinfo=TZ),
        end=datetime(2026, 10, 16, 21, 0, tzinfo=TZ),
        state=SLOT_FREE,
        creneau_id="56132",
    )


class FakeResponse:
    def __init__(self, body, url, status=200):
        if not isinstance(body, str):
            body = json.dumps(body)
        self._body, self.url, self.status = body, URL(url), status

    async def text(self):
        return self._body

    async def read(self):
        return self._body.encode()

    async def json(self, content_type=None):
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


def body_of(session, part):
    """The JSON we sent to the first call whose URL contains ``part``."""
    for method, url, kwargs in session.calls:
        if part in url and kwargs.get("data"):
            return json.loads(kwargs["data"])
    raise AssertionError(f"no body sent to {part}")


def client_for(routes, cookie="SHARED_SESSION_DRUPAL=abc"):
    session = FakeSession(routes)
    return TenupClient(session, cookie, "50690472", TZ), session




SESSION_NAME = "SHARED_SESSION_JAVA"
SESSION_VALUE = "f1e2d3c4-0000-4a5b-8c9d-0e1f2a3b4c5d"


def test_session_cookie_reports_what_the_jar_holds():
    async def go():
        client, _ = client_for({}, cookie=f"{SESSION_NAME}={SESSION_VALUE}")
        assert client.session_cookie == f"{SESSION_NAME}={SESSION_VALUE}"

    run(go)


def test_session_cookie_follows_a_rotation_by_tenup():
    """Ten'Up can hand out a new session id while we are using it.

    The jar follows; the config entry would still hold what the user pasted, and
    the next restart would go back to a session that has been replaced.
    """
    async def go():
        client, _ = client_for({}, cookie=f"{SESSION_NAME}={SESSION_VALUE}")
        client.session.cookie_jar.update_cookies(
            {SESSION_NAME: "99999999-1111-4222-8333-444444444444"},
            URL("https://tenup.fft.fr"),
        )
        assert client.session_cookie.endswith("99999999-1111-4222-8333-444444444444")

    run(go)


def test_session_cookie_ignores_everything_else_the_site_sets():
    """A tracker or a waiting-room token is not a session and must never be stored."""
    async def go():
        client, _ = client_for({}, cookie=f"{SESSION_NAME}={SESSION_VALUE}")
        client.session.cookie_jar.update_cookies(
            {"datadome": "abc", "userStore": "%7B%7D", "PREFERRED_PRATIQUE": "x"},
            URL("https://tenup.fft.fr"),
        )
        assert client.session_cookie == f"{SESSION_NAME}={SESSION_VALUE}"

    run(go)


def test_session_cookie_is_none_without_a_session():
    """Nothing to write back beats writing back a cookie that signs nobody in."""
    async def go():
        client, _ = client_for({}, cookie="datadome=abc")
        assert client.session_cookie is None

    run(go)


def test_the_cookie_that_was_replaced_is_never_written_back():
    """An entry that predates the rebuild still holds it; it is not a session."""
    async def go():
        client, _ = client_for({}, cookie="SHARED_SESSION_DRUPAL=aae6fe4e-0700-49d0-84ea-7b283f14affa")
        assert client.session_cookie is None

    run(go)


# ------------------------------------------------------------------- planning
def test_the_planning_is_asked_for_one_day_of_one_club():
    def scenario():
        client, session = client_for(
            {
                ("GET", "/profil"): [FakeResponse(PROFILE, "https://tenup.fft.fr/api/back/v1/profil")],
                ("GET", "/clubs/reservations"): [
                    FakeResponse(PLANNING, "https://tenup.fft.fr/api/back/v1/clubs/reservations")
                ],
            }
        )
        return client, session

    async def go():
        client, session = scenario()
        planning = await client.async_get_planning(date(2026, 10, 16))
        assert [c.name for c in planning.courts] == ["PLATRE 1"]
        assert len(planning.free_slots) == 1
        asked = [url for _m, url, _k in session.calls if "clubs/reservations" in url][0]
        assert "date=2026-10-16" in asked and "codeClub=50690472" in asked

    run(go)


def test_who_we_are_is_fetched_once_and_kept():
    """Every day of the grid needs it; asking again each time would be rude."""
    async def go():
        client, session = client_for(
            {
                ("GET", "/profil"): [FakeResponse(PROFILE, "https://tenup.fft.fr/api/back/v1/profil")],
                ("GET", "/clubs/reservations"): [
                    FakeResponse(PLANNING, "https://tenup.fft.fr/api/back/v1/clubs/reservations")
                ],
            }
        )
        await client.async_get_planning(date(2026, 10, 16))
        await client.async_get_planning(date(2026, 10, 17))
        assert len([url for _m, url, _k in session.calls if url.endswith("/profil")]) == 1

    run(go)


def test_the_cookie_lands_in_the_jar():
    async def go():
        client, _ = client_for({})
        assert any(m.key == "SHARED_SESSION_DRUPAL" for m in client.session.cookie_jar)

    run(go)


# ----------------------------------------------------------------------- auth
@pytest.mark.parametrize("status", [401, 403])
def test_a_refused_call_asks_for_a_new_cookie(status):
    async def go():
        client, _ = client_for(
            {("GET", "/profil"): [FakeResponse({}, "https://tenup.fft.fr/api/back/v1/profil", status)]}
        )
        with pytest.raises(TenupAuthError):
            await client.async_profile()

    run(go)


def test_the_sign_in_page_is_a_dead_cookie_too():
    """Ten'Up answers HTML, not 401, when it decides to send us to sign in."""
    async def go():
        client, _ = client_for(
            {
                ("GET", "/profil"): [
                    FakeResponse(
                        "<!doctype html><html><body>Connexion</body></html>",
                        "https://tenup.fft.fr/auth/signin?callbackUrl=%2Fprofil",
                    )
                ]
            }
        )
        with pytest.raises(TenupAuthError):
            await client.async_profile()

    run(go)


def test_a_wall_in_front_of_the_site_is_not_an_expired_session():
    """A bot challenge proves nothing about the cookie; asking for a new one would be wrong."""
    async def go():
        client, _ = client_for(
            {
                ("GET", "/profil"): [
                    FakeResponse(
                        "<html><body>captcha-delivery</body></html>",
                        "https://tenup.fft.fr/api/back/v1/profil",
                    )
                ]
            }
        )
        with pytest.raises(TenupConnectionError):
            await client.async_profile()

    run(go)


def test_a_server_error_is_never_a_cookie_problem():
    async def go():
        client, _ = client_for(
            {("GET", "/profil"): [FakeResponse({}, "https://tenup.fft.fr/api/back/v1/profil", 503)]}
        )
        with pytest.raises(TenupConnectionError):
            await client.async_profile()

    run(go)


def test_queue_it_is_passed_once_then_retried():
    async def go():
        client, session = client_for(
            {
                ("GET", "/profil"): [
                    FakeResponse("file d'attente", "https://tenup.queue-it.net/?c=tenup"),
                    FakeResponse(PROFILE, "https://tenup.fft.fr/api/back/v1/profil"),
                ],
                ("POST", "queue-it.net/spa-api"): [
                    FakeResponse(
                        {"redirectUrl": "https://tenup.fft.fr/?queueittoken=x"},
                        "https://tenup.queue-it.net/spa-api",
                    )
                ],
                ("GET", "queueittoken"): [
                    FakeResponse("ok", "https://tenup.fft.fr/")
                ],
            }
        )
        assert (await client.async_profile())["id"] == ME
        assert any("spa-api" in url for _m, url, _k in session.calls)

    run(go)


def test_a_waiting_room_that_never_opens_is_an_error():
    async def go():
        client, _ = client_for(
            {
                ("GET", "/profil"): [
                    FakeResponse("file", "https://tenup.queue-it.net/?c=tenup"),
                    FakeResponse("file", "https://tenup.queue-it.net/?c=tenup"),
                ],
                ("POST", "queue-it.net/spa-api"): [
                    FakeResponse(
                        {"redirectUrl": "https://tenup.fft.fr/?queueittoken=x"},
                        "https://tenup.queue-it.net/spa-api",
                    )
                ],
                ("GET", "queueittoken"): [FakeResponse("ok", "https://tenup.fft.fr/")],
            }
        )
        with pytest.raises(TenupConnectionError):
            await client.async_profile()

    run(go)


# ------------------------------------------------------------------- partners
def test_a_partner_search_sends_one_word_and_the_club_code():
    async def go():
        client, session = client_for(
            {
                ("POST", "personnes/recherche"): [
                    FakeResponse(
                        {"total": 1, "hits": [{"idCrm": FRIEND, "nom": "ROE", "prenom": "Robin"}]},
                        "https://tenup.fft.fr/api/back/v1/personnes/recherche/reservations-adherents",
                    )
                ]
            }
        )
        found = await client.async_search_partner("Robin ROE")
        assert [p.name for p in found] == ["Robin ROE"]
        sent = body_of(session, "personnes/recherche")
        assert sent == {"query": "robin", "codesClubs": ["50690472"], "from": 0, "size": 10}

    run(go)


def test_a_search_too_short_never_reaches_tenup():
    async def go():
        client, session = client_for({})
        with pytest.raises(TenupBookingError):
            await client.async_search_partner("ro")
        assert session.calls == []

    run(go)


# -------------------------------------------------------------------- booking
def booking_routes(mine, theirs=None, answer=None):
    routes = {
        ("GET", "/profil"): [FakeResponse(PROFILE, "https://tenup.fft.fr/api/back/v1/profil")],
        ("POST", "reservations/eligibilite"): [
            FakeResponse(mine, "https://tenup.fft.fr/api/back/v1/clubs/reservations/eligibilite")
        ],
        ("POST", "reservations/paiement"): [
            FakeResponse(
                answer if answer is not None else {"idReservation": 170000005},
                "https://tenup.fft.fr/api/back/v1/clubs/reservations/paiement",
            )
        ],
    }
    if theirs is not None:
        routes[("POST", "reservations/eligibilite")].append(
            FakeResponse(theirs, "https://tenup.fft.fr/api/back/v1/clubs/reservations/eligibilite")
        )
    return routes


def test_a_single_player_booking_sends_the_slot_and_our_subscription():
    async def go():
        client, session = client_for(booking_routes(eligibility(offer(11, "AB"))))
        slot = free_slot()
        assert "confirm" in (await client.async_book(slot)).lower()
        sent = body_of(session, "reservations/paiement")
        assert sent["codeClub"] == "50690472"
        assert sent["idCreneau"] == 56132
        assert sent["date"] == "2026-10-16"
        assert sent["heureDebut"] == "20:00:00" and sent["heureFin"] == "21:00:00"
        assert sent["personnes"] == [
            {
                "idCrm": ME,
                "idAdhesion": 11,
                "email": None,
                "invite": False,
                "ticketPayant": False,
                "nomJoueurSaisi": None,
            }
        ]
        assert slot.reservation_id == "170000005"

    run(go)


def test_a_booking_never_carries_a_price_nor_a_paid_ticket():
    """The guard that matters: nothing we send may ever charge the user."""
    async def go():
        client, session = client_for(booking_routes(eligibility(offer(11, "AB"))))
        await client.async_book(free_slot())
        sent = body_of(session, "reservations/paiement")
        assert sent["montant"] == 0
        assert all(person["ticketPayant"] is False for person in sent["personnes"])
        assert all(person["invite"] is False for person in sent["personnes"])
        assert "urlPaiement" not in sent, "a free booking never opens a payment"

    run(go)


def test_a_ticket_book_is_never_picked_even_when_it_is_the_only_offer():
    """Ten'Up offers it next to the subscription; taking it would spend a ticket."""
    async def go():
        client, session = client_for(booking_routes(eligibility(offer(22, "CA"))))
        with pytest.raises(TenupBookingError, match="gratuite"):
            await client.async_book(free_slot())
        assert not any("paiement" in url for _m, url, _k in session.calls)

    run(go)


def test_the_reason_the_club_gives_is_relayed_when_no_offer_is_free():
    async def go():
        client, _ = client_for(
            booking_routes(eligibility(offer(11, "AB", eligible=False, erreur="Quota atteint")))
        )
        with pytest.raises(TenupBookingError, match="Quota atteint"):
            await client.async_book(free_slot())

    run(go)


def test_a_court_for_two_refuses_to_book_alone():
    async def go():
        client, session = client_for(booking_routes(eligibility(offer(11, "AB", players=2))))
        with pytest.raises(TenupBookingError, match="2 joueurs"):
            await client.async_book(free_slot())
        assert not any("paiement" in url for _m, url, _k in session.calls)

    run(go)


def test_a_court_for_two_sends_both_players_on_their_own_subscription():
    async def go():
        client, session = client_for(
            booking_routes(
                eligibility(offer(11, "AB", players=2)),
                theirs=eligibility(offer(33, "AB", players=2), id_crm=FRIEND),
            )
        )
        partner = Partner(id_crm=FRIEND, last_name="ROE", first_name="Robin")
        await client.async_book(free_slot(), partner)
        sent = body_of(session, "reservations/paiement")
        assert [p["idCrm"] for p in sent["personnes"]] == [ME, FRIEND]
        assert [p["idAdhesion"] for p in sent["personnes"]] == [11, 33]

    run(go)


def test_the_partner_offers_are_asked_for_under_their_own_id():
    async def go():
        client, session = client_for(
            booking_routes(
                eligibility(offer(11, "AB", players=2)),
                theirs=eligibility(offer(33, "AB", players=2), id_crm=FRIEND),
            )
        )
        await client.async_book(
            free_slot(), Partner(id_crm=FRIEND, last_name="ROE", first_name="Robin")
        )
        bodies = [
            json.loads(kwargs["data"])
            for _m, url, kwargs in session.calls
            if "eligibilite" in url
        ]
        assert bodies[0] == {
            "idCourt": 37195,
            "codeClub": "50690472",
            "date": "2026-10-16",
            "heureDebut": "20:00:00",
            "heureFin": "21:00:00",
            "formulaire": True,
        }
        assert bodies[1]["idCrm"] == FRIEND and bodies[1]["formulaire"] is False

    run(go)


def test_a_partner_without_a_free_offer_stops_the_booking():
    async def go():
        client, session = client_for(
            booking_routes(
                eligibility(offer(11, "AB", players=2)),
                theirs=eligibility(offer(44, "CA", players=2), id_crm=FRIEND),
            )
        )
        with pytest.raises(TenupBookingError, match="Robin ROE"):
            await client.async_book(
                free_slot(), Partner(id_crm=FRIEND, last_name="ROE", first_name="Robin")
            )
        assert not any("paiement" in url for _m, url, _k in session.calls)

    run(go)


def test_a_refusal_stated_by_tenup_is_relayed():
    async def go():
        client, _ = client_for(
            booking_routes(
                eligibility(offer(11, "AB")),
                answer={"errorMessage": "Vous avez déjà une réservation en cours"},
            )
        )
        with pytest.raises(TenupBookingError, match="déjà une réservation"):
            await client.async_book(free_slot())

    run(go)


# ---------------------------------------------------------------- cancelling
def test_a_cancellation_deletes_the_reservation_by_id():
    async def go():
        client, session = client_for(
            {("DELETE", "/reservations/"): [FakeResponse("", "https://tenup.fft.fr/api/back/v1/reservations/170000005", 204)]}
        )
        slot = free_slot()
        slot.reservation_id = "170000005"
        await client.async_cancel(slot)
        assert session.calls[0][0] == "DELETE"
        assert session.calls[0][1].endswith("/reservations/170000005")

    run(go)


def test_a_cancellation_without_a_reservation_never_calls_tenup():
    async def go():
        client, session = client_for({})
        with pytest.raises(TenupBookingError):
            await client.async_cancel(free_slot())
        assert session.calls == []

    run(go)


def test_a_cancellation_on_a_dead_session_still_asks_for_a_cookie():
    async def go():
        client, _ = client_for(
            {("DELETE", "/reservations/"): [FakeResponse({}, "https://tenup.fft.fr/api/back/v1/reservations/1", 401)]}
        )
        slot = free_slot()
        slot.reservation_id = "1"
        with pytest.raises(TenupAuthError):
            await client.async_cancel(slot)

    run(go)


def test_required_players_swallows_a_hiccup():
    """It only decorates the grid: a failure must never fail the refresh."""
    async def go():
        client, _ = client_for(
            {
                ("POST", "reservations/eligibilite"): [
                    FakeResponse({}, "https://tenup.fft.fr/api/back/v1/clubs/reservations/eligibilite", 503)
                ]
            }
        )
        assert await client.async_required_players(free_slot()) is None

    run(go)
