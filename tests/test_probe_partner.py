"""The probe's URL builders are pure: pin them before trusting the field test."""

import pytest

from custom_components.tenup.api import (
    PARTNER_AUTOCOMPLETE_PATH,
    formule_ajax_candidates,
    partner_autocomplete_candidates,
)


def test_autocomplete_tries_the_drupal_path_form_first():
    urls = partner_autocomplete_candidates("Moss")
    assert urls[0] == f"{PARTNER_AUTOCOMPLETE_PATH}/Moss"
    assert len(urls) == len(set(urls)) == 5


def test_autocomplete_honours_the_path_advertised_by_the_page():
    # beta.1 hardcoded the fixture's path and every attempt 404'd; the page
    # advertises its own, so the builder must use it.
    urls = partner_autocomplete_candidates("Moss", "/club/autocomplete/partenaire")
    assert urls[0] == "/club/autocomplete/partenaire/Moss"
    assert all("/adherent/" not in u for u in urls)


@pytest.mark.parametrize(
    "given", ["adherent/autocomplete/partenaire", "/adherent/autocomplete/partenaire/"]
)
def test_autocomplete_normalises_the_page_path(given):
    assert partner_autocomplete_candidates("Moss", given)[0] == (
        f"{PARTNER_AUTOCOMPLETE_PATH}/Moss"
    )


def test_autocomplete_escapes_the_query():
    urls = partner_autocomplete_candidates("Le Moore")
    assert " " not in "".join(urls)
    assert "Le%20Gassy" in urls[0]


@pytest.mark.parametrize("bad", ["", "   "])
def test_autocomplete_refuses_an_empty_query(bad):
    with pytest.raises(ValueError):
        partner_autocomplete_candidates(bad)


def test_formule_ajax_covers_the_plausible_bases_without_duplicates():
    urls = formule_ajax_candidates("/club/reservations/detail/12345", "formule/ajax")
    assert urls == [
        "/club/reservations/formule/ajax",
        "/club/formule/ajax",
        "/formule/ajax",
        "/club/reservations/detail/formule/ajax",
    ]


def test_formule_ajax_dedupes_when_the_page_base_repeats_a_fixed_base():
    urls = formule_ajax_candidates("/club/reservations/12345", "formule/ajax")
    assert urls == [
        "/club/reservations/formule/ajax",
        "/club/formule/ajax",
        "/formule/ajax",
    ]
    assert len(urls) == len(set(urls))


def test_formule_ajax_is_empty_without_a_fragment():
    assert formule_ajax_candidates("/club/reservations/detail/1", "") == []
    assert formule_ajax_candidates("/club/reservations/detail/1", "/") == []
