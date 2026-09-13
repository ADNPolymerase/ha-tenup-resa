"""Reading the two answers the 2-player flow depends on."""

import pytest

from custom_components.tenup.parser import (
    BookingForm,
    TenupParseError,
    parse_formules_response,
    parse_partner_results,
)

# Ce que Ten'Up a reellement renvoye le 2026-09-13.
AUTOCOMPLETE = (
    '{"Eric DOE (222222222)":"Eric DOE",'
    '"John DOE (111111111)":"John DOE"}'
)
FORMULES = (
    '"{\\u0022formules\\u0022:[{\\u0022attr\\u0022:17761992,\\u0022value\\u0022:17761992,'
    '\\u0022label\\u0022:\\u0022Adultes 2027\\u0022,\\u0022disabled\\u0022:false},'
    '{\\u0022attr\\u0022:17794189,\\u0022value\\u0022:17794189,'
    '\\u0022label\\u0022:\\u0022Tickets adh\\\\u00e9rents\\u0022,\\u0022disabled\\u0022:false}],'
    '\\u0022ticketRestants\\u0022:{\\u002217794189\\u0022:5}}"'
)


def test_partner_results_keep_the_key_that_carries_the_licence():
    out = parse_partner_results(AUTOCOMPLETE)
    assert out == [
        ("Eric DOE (222222222)", "Eric DOE"),
        ("John DOE (111111111)", "John DOE"),
    ]
    # le pere et le fils ne se distinguent que par la cle
    assert out[0][1] != out[1][1] and out[0][0] != out[1][0]


def test_partner_results_on_an_empty_search():
    assert parse_partner_results("{}") == []


@pytest.mark.parametrize("bad", ["<!DOCTYPE html>", "[]", ""])
def test_partner_results_refuse_a_non_object(bad):
    with pytest.raises(TenupParseError):
        parse_partner_results(bad)


def test_formules_response_is_decoded_twice():
    out = parse_formules_response(FORMULES)
    assert [f["label"] for f in out] == ["Adultes 2027", "Tickets adhérents"]
    assert out[0]["value"] == 17761992


def test_formules_response_accepts_a_plain_object_too():
    assert parse_formules_response('{"formules": [{"value": 1, "label": "X"}]}') == [
        {"value": 1, "label": "X"}
    ]


def test_formules_response_raises_on_the_error_shape():
    with pytest.raises(TenupParseError, match="technique"):
        parse_formules_response('{"erreur":"Une erreur technique est survenue."}')
    with pytest.raises(TenupParseError):
        parse_formules_response('"{\\u0022formules\\u0022:[],\\u0022erreur\\u0022:\\u0022zut\\u0022}"')


def _form(**kw):
    base = dict(
        player_name="J.Public", formula_id="18332791", submit_data="abc",
        required_players=2, partner_fields=[],
    )
    base.update(kw)
    return BookingForm(**base)


def test_post_data_stays_single_player_when_no_partner_is_set():
    data = _form().as_post_data()
    assert "joueur2_nom" not in data and "joueur2_formule" not in data
    assert data["joueur1_nom"] == "J.Public"


def test_post_data_carries_the_partner_choice_and_formula():
    data = _form(
        partner_choice="John DOE (111111111)", partner_formula="17761992"
    ).as_post_data()
    assert data["joueur2_nom"] == "John DOE (111111111)"
    assert data["joueur2_formule"] == "17761992"
    # le joueur 1 n est pas altere
    assert data["joueur1_formule"] == "18332791"
    assert data["reservation_detail_submit"] == "Suivant"


RESULTS = [
    ("Eric DOE (222222222)", "Eric DOE"),
    ("John DOE (111111111)", "John DOE"),
    ("Richard ROE (333333333)", "Richard ROE"),
]


def test_resolve_partner_takes_an_exact_stored_choice():
    from custom_components.tenup.parser import resolve_partner

    assert resolve_partner(RESULTS, "John DOE (111111111)") == [
        ("John DOE (111111111)", "John DOE")
    ]


def test_resolve_partner_returns_both_homonyms_for_a_bare_surname():
    from custom_components.tenup.parser import resolve_partner

    out = resolve_partner(RESULTS, "DOE")
    assert len(out) == 2  # le pere et le fils: il faudra demander
    assert resolve_partner(RESULTS, "John Doe") == [
        ("John DOE (111111111)", "John DOE")
    ]


def test_resolve_partner_ignores_case_and_accents_and_unknown_names():
    from custom_components.tenup.parser import resolve_partner

    assert resolve_partner([("Jose GOMEZ (1)", "José GOMEZ")], "jose gomez")
    assert resolve_partner(RESULTS, "MOSS") == []
    assert resolve_partner(RESULTS, "   ") == []


def test_free_formulas_removes_anything_that_costs_money():
    from custom_components.tenup.parser import free_formulas

    out = free_formulas([
        {"value": 17761992, "label": "Adultes 2027", "disabled": False},
        {"value": "UNITAIRE - 18332791", "label": "Ticket à l'unité (6€)", "prix": 6},
        {"value": 999, "label": "Payante sans mention UNITAIRE", "prix": 3},
        {"value": 111, "label": "Indisponible", "disabled": True},
    ])
    assert [f["label"] for f in out] == ["Adultes 2027"]


def test_free_formulas_keeps_a_zero_price_and_survives_a_bad_price():
    from custom_components.tenup.parser import free_formulas

    assert len(free_formulas([{"value": 1, "label": "Gratuite", "prix": 0}])) == 1
    assert free_formulas([{"value": 2, "label": "Prix illisible", "prix": "six"}]) == []


def test_free_formulas_rejects_unitaire_even_without_an_announced_price():
    from custom_components.tenup.parser import free_formulas

    # Sans cette assertion, la garde UNITAIRE n est jamais eprouvee seule:
    # l exemple a 6 EUR est deja ecarte par le filtre sur le prix.
    assert free_formulas([
        {"value": "UNITAIRE - 18332791", "label": "Ticket a l unite"},
    ]) == []


def test_partner_search_term_sends_a_word_the_site_answers_to():
    from custom_components.tenup.parser import partner_search_term

    # Mesure du 2026-09-13: /club/autocomplete/partenaire/John repond bien,
    # donc l autocompletion matche le prenom comme le nom de famille.
    assert partner_search_term("John DOE (111111111)") == "DOE"
    assert partner_search_term("DOE") == "DOE"
    assert partner_search_term("Richard ROE") == "Richard"
    # L ancienne liste de JD contient "J. DOE": l initiale est trop courte
    # pour etre cherchee, c est le nom qu il faut envoyer.
    assert partner_search_term("J. DOE") == "DOE"


def test_partner_search_term_falls_back_when_every_word_is_too_short():
    from custom_components.tenup.parser import partner_search_term

    assert partner_search_term("Li Wu") == "Li Wu"
