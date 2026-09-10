from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from custom_components.tenup.api import parse_cookie_header
from custom_components.tenup.const import SLOT_BUSY, SLOT_FREE, SLOT_MINE
from custom_components.tenup.parser import (
    TenupParseError,
    extract_drupal_settings,
    is_logged_in,
    parse_book_path,
    parse_booking_form,
    parse_messages,
    parse_planning,
)

FIXTURES = Path(__file__).parent / "fixtures"
TZ = timezone(timedelta(hours=2))


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_planning_courts_and_states():
    planning = parse_planning(load("planning.html"), date(2026, 9, 10), TZ)
    assert planning.logged_in
    assert [c.id for c in planning.courts] == ["21099", "21100"]
    assert [c.name for c in planning.courts] == ["Court COUVERT", "COURT 1"]
    assert planning.window_start == datetime(2026, 8, 26, 0, 0, tzinfo=TZ)
    assert planning.window_end == datetime(2026, 9, 16, 0, 0, tzinfo=TZ)

    by_id = {s.slot_id: s for s in planning.slots}
    assert len(by_id) == 7

    past = by_id["21099_0800"]
    assert past.state == SLOT_BUSY and past.label is None

    busy = by_id["21099_0900"]
    assert busy.state == SLOT_BUSY
    assert busy.label == "B. GREEN A. GREEN"

    free = by_id["21099_1000"]
    assert free.state == SLOT_FREE
    assert free.book_path.startswith("/club/reservation_court_add/nojs/21099/56086/")
    assert free.creneau_id == "56086"  # idCreneau, the (court + time band) config key
    assert free.required_players is None  # unknown until the coordinator looks it up
    assert free.as_dict()["required_players"] is None
    assert by_id["21100_2000"].creneau_id == "56152"
    assert free.court_name == "Court COUVERT"
    assert free.start == datetime(2026, 9, 10, 10, 0, tzinfo=TZ)
    assert free.end == datetime(2026, 9, 10, 11, 0, tzinfo=TZ)

    mine = by_id["21100_2100"]
    assert mine.state == SLOT_MINE
    assert mine.label == "J. PUBLIC"
    assert mine.reservation_id == "165841846"
    assert mine.cancel_path.startswith("/club/reservation_court_delete/nojs/87654321/165841846/21100/2100")
    assert mine.hhmm == "2100"

    half = by_id["21100_2200"]
    assert half.state == SLOT_FREE
    assert half.end == datetime(2026, 9, 10, 22, 30, tzinfo=TZ)  # row-30 wins over the truncated data-end-ts

    lesson = by_id["21100_1130"]
    assert lesson.state == SLOT_BUSY
    assert lesson.start == datetime(2026, 9, 10, 11, 30, tzinfo=TZ)
    assert lesson.end == datetime(2026, 9, 10, 13, 0, tzinfo=TZ)
    assert lesson.label == "CJ sam 11h30 Alex Robin"

    assert [s.slot_id for s in planning.free_slots] == ["21099_1000", "21100_2000", "21100_2200"]
    assert [s.slot_id for s in planning.my_slots] == ["21100_2100"]
    assert planning.find("21100", datetime(2026, 9, 10, 20, 0, tzinfo=TZ)).slot_id == "21100_2000"
    assert planning.find("21100", datetime(2026, 9, 10, 23, 0, tzinfo=TZ)) is None


def test_logged_in_detection():
    html = load("planning.html")
    assert html.index("<body") > 20000  # the body comes after a large head, like the real pages
    assert is_logged_in(html)
    assert not is_logged_in(load("planning.html").replace("logged-in", "not-logged-in"))
    assert not is_logged_in("<html><body class='html'></body></html>")


def test_booking_form():
    form = parse_booking_form(load("detail.html"))
    assert form.player_name == "John Adam PUBLIC"
    assert form.formula_id == "18332791"
    assert form.required_players == 1
    assert form.partner_fields == []
    assert '"idCourt":"21100"' in form.submit_data
    data = form.as_post_data()
    assert data["reservation_detail_submit"] == "Suivant"
    assert set(data) == {"joueur1_nom", "joueur1_formule", "submit_data", "reservation_detail_submit"}


def test_booking_form_two_players():
    html = load("detail.html").replace("demande 1 joueur", "demande 2 joueurs")
    assert parse_booking_form(html).required_players == 2


def test_booking_form_missing():
    with pytest.raises(TenupParseError):
        parse_booking_form("<html><body>nothing</body></html>")


def test_messages():
    messages = parse_messages(load("detail_error.html"))
    assert len(messages) == 1
    assert messages[0].startswith("Réservation impossible.")
    assert "Message d'erreur" not in messages[0]
    assert parse_messages(load("planning.html")) == []


def test_drupal_settings_with_braces_inside_strings():
    html = load("detail.html")
    settings = extract_drupal_settings(html)
    assert "tc_events_19" in settings["reservation_detail"]["form"]["fields"]["submit"]["attributes"]["onclick"]


def test_book_path():
    assert parse_book_path("/club/reservation_court_add/nojs/21100/56152/1789066800/1789070400?no_next=1") == (
        "21100", "56152", 1789066800, 1789070400)
    assert parse_book_path("/club/other") is None


def test_cookie_header():
    assert parse_cookie_header("SESSabc=123") == {"SESSabc": "123"}
    assert parse_cookie_header("Cookie: SESSabc=123; datadome=xyz") == {"SESSabc": "123", "datadome": "xyz"}
    with pytest.raises(ValueError):
        parse_cookie_header("   ")


def test_cookie_candidates():
    from custom_components.tenup.api import SESSION_COOKIE_NAMES, cookie_candidates

    assert cookie_candidates("SESSabc=123") == ["SESSabc=123"]
    assert cookie_candidates("Cookie: SESSabc=123; datadome=x") == ["SESSabc=123; datadome=x"]
    bare = cookie_candidates("  abc-DEF_123\n")
    assert bare == [f"{name}=abc-DEF_123" for name in SESSION_COOKIE_NAMES]
    assert bare[0].startswith("SSESS7ba44afc36c80c3faa2b8fa87e7742c5=")
    assert bare[1].startswith("SESS7ba44afc36c80c3faa2b8fa87e7742c5=")
    assert len(bare) == 10
    with pytest.raises(ValueError):
        cookie_candidates("not a cookie value!")
    with pytest.raises(ValueError):
        cookie_candidates("   ")
