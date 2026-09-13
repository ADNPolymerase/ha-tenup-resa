"""The probe's URL builders are pure: pin them before trusting the field test."""

import pytest

from custom_components.tenup.api import (
    PARTNER_AUTOCOMPLETE_PATH,
    formule_ajax_candidates,
    partner_autocomplete_candidates,
)


def test_autocomplete_tries_path_form_first():
    urls = partner_autocomplete_candidates("Moss")
    assert urls[0] == f"{PARTNER_AUTOCOMPLETE_PATH}/Moss"
    assert len(urls) == len(set(urls)) == 5
    assert all(u.startswith(PARTNER_AUTOCOMPLETE_PATH) for u in urls)


def test_autocomplete_escapes_the_query():
    # A surname with a space or an accent must not break the URL.
    urls = partner_autocomplete_candidates("Le Moore")
    assert "%20" in urls[0] or "Le%20Gassy" in urls[0]
    assert " " not in "".join(urls)


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


def test_formule_ajax_is_empty_without_a_fragment():
    assert formule_ajax_candidates("/club/reservations/detail/1", "") == []
    assert formule_ajax_candidates("/club/reservations/detail/1", "/") == []


def test_formule_ajax_dedupes_when_the_page_base_repeats_a_fixed_base():
    # book_path already sits in /club/reservations/, so its base collides.
    urls = formule_ajax_candidates("/club/reservations/12345", "formule/ajax")
    assert urls == [
        "/club/reservations/formule/ajax",
        "/club/formule/ajax",
        "/formule/ajax",
    ]
    assert len(urls) == len(set(urls))
