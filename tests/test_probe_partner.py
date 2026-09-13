"""The probe's pure helpers: pin them before trusting a field test."""

import pytest

from custom_components.tenup.api import (
    PARTNER_AUTOCOMPLETE_PATH,
    find_snippets,
    formule_ajax_candidates,
    partner_autocomplete_candidates,
    script_urls,
)


def test_autocomplete_sweeps_the_bases_a_custom_component_might_use():
    assert partner_autocomplete_candidates("Moss") == [
        "/adherent/autocomplete/partenaire/Moss",
        "/club/reservations/adherent/autocomplete/partenaire/Moss",
        "/club/adherent/autocomplete/partenaire/Moss",
        "/back/v2/adherent/autocomplete/partenaire/Moss",
        "/fr/adherent/autocomplete/partenaire/Moss",
    ]


def test_autocomplete_honours_the_path_advertised_by_the_page():
    urls = partner_autocomplete_candidates("Moss", "/club/autocomplete/xyz")
    assert urls[0] == "/club/autocomplete/xyz/Moss"
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


def test_script_urls_keeps_only_js_and_absolutises():
    html = (
        '<script src="/sites/default/files/a.js"></script>'
        '<script src="https://cdn.example.com/b.js?v=2"></script>'
        '<script src="/themes/style.css"></script>'
        "<script>var inline = 1</script>"
    )
    assert script_urls(html) == [
        "https://tenup.fft.fr/sites/default/files/a.js",
        "https://cdn.example.com/b.js?v=2",
    ]


def test_script_urls_dedupes_and_respects_the_limit():
    html = '<script src="/a.js"></script>' * 3 + '<script src="/b.js"></script>'
    assert script_urls(html) == ["https://tenup.fft.fr/a.js", "https://tenup.fft.fr/b.js"]
    assert script_urls(html, limit=1) == ["https://tenup.fft.fr/a.js"]


def test_find_snippets_bounds_each_hit_and_respects_the_limit():
    text = "x" * 500 + "NEEDLE" + "y" * 500 + "NEEDLE" + "z" * 500
    one = find_snippets(text, "NEEDLE", radius=10, limit=1)
    assert len(one) == 1 and "NEEDLE" in one[0]
    assert len(one[0]) <= 10 + len("NEEDLE") + 10
    assert len(find_snippets(text, "NEEDLE", radius=10)) == 2
    assert find_snippets(text, "ABSENT") == []


def test_formule_ajax_covers_the_plausible_bases_without_duplicates():
    assert formule_ajax_candidates("/club/reservations/detail/12345", "formule/ajax") == [
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
