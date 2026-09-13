"""The probe's pure helpers: pin them before trusting a field test."""

import pytest

from custom_components.tenup.api import (
    JOUEUR_AUTOCOMPLETE_PATH,
    PARTNER_AUTOCOMPLETE_PATH,
    find_snippets,
    formule_ajax_candidates,
    partner_autocomplete_candidates,
    script_urls,
)


def test_autocomplete_calls_the_url_the_bundle_hardcodes_first():
    # RechercheJoueurAutocomplete ignores autocomplete_path and calls this.
    urls = partner_autocomplete_candidates("Moss")
    assert urls[0] == f"{JOUEUR_AUTOCOMPLETE_PATH}/Moss"
    assert urls == [
        "/club/autocomplete/partenaire/Moss",
        "/club/autocomplete/partenaire/Moss?term=Moss",
        "/club/reservations/adherent/autocomplete/partenaire/Moss",
        "/adherent/autocomplete/partenaire/Moss",
    ]


def test_autocomplete_still_keeps_the_advertised_path_as_a_fallback():
    urls = partner_autocomplete_candidates("Moss", "/club/autocomplete/xyz")
    assert urls[0] == f"{JOUEUR_AUTOCOMPLETE_PATH}/Moss"
    assert "/club/autocomplete/xyz/Moss" in urls


@pytest.mark.parametrize(
    "given", ["adherent/autocomplete/partenaire", "/adherent/autocomplete/partenaire/"]
)
def test_autocomplete_normalises_the_page_path(given):
    assert f"{PARTNER_AUTOCOMPLETE_PATH}/Moss" in partner_autocomplete_candidates(
        "Moss", given
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


def test_parse_partner_choice_splits_name_and_licence():
    from custom_components.tenup.api import parse_partner_choice

    assert parse_partner_choice("John DOE (111111111)") == ("John DOE", "111111111")
    # The father and the son differ only by the identifier.
    assert parse_partner_choice("Eric DOE (222222222)") == ("Eric DOE", "222222222")
    assert parse_partner_choice("Richard ROE (1234)") == ("Richard ROE", "1234")


def test_parse_partner_choice_refuses_a_label_without_an_identifier():
    from custom_components.tenup.api import parse_partner_choice

    assert parse_partner_choice("J. DOE") is None
    assert parse_partner_choice("John DOE ()") is None
    assert parse_partner_choice("John DOE (abc)") is None


def test_partner_post_variants_keep_the_base_and_add_one_shape_each():
    from custom_components.tenup.api import partner_post_variants

    base = {"codeClub": "87654321", "idCourt": "21099"}
    variants = partner_post_variants(base, "John DOE (111111111)")
    assert len(variants) == 5
    for payload in variants:
        assert payload["codeClub"] == "87654321" and payload["idCourt"] == "21099"
    assert variants[0]["joueur2_nom"] == "John DOE (111111111)"
    assert variants[1]["idPartenaire"] == "111111111"
    assert base == {"codeClub": "87654321", "idCourt": "21099"}  # jamais mute


def test_partner_post_variants_is_empty_without_an_identifier():
    from custom_components.tenup.api import partner_post_variants

    assert partner_post_variants({"a": "b"}, "J. DOE") == []


def test_json_payload_variants_starts_without_the_partner():
    from custom_components.tenup.api import json_payload_variants

    base = {"codeClub": "87654321", "ticketAutorises": True}
    out = json_payload_variants(base, "John DOE (111111111)")
    assert [label for label, _ in out] == ["sans partenaire", "joueur2_nom", "idPartenaire"]
    assert "joueur2_nom" not in out[0][1] and "idPartenaire" not in out[0][1]
    assert out[1][1]["joueur2_nom"] == "John DOE (111111111)"
    assert out[2][1]["idPartenaire"] == "111111111"
    # JSON garde les types natifs, contrairement au form-encode
    assert out[0][1]["ticketAutorises"] is True
    assert base == {"codeClub": "87654321", "ticketAutorises": True}


def test_json_payload_variants_without_a_usable_partner_keeps_the_bare_body():
    from custom_components.tenup.api import json_payload_variants

    assert [l for l, _ in json_payload_variants({"a": 1}, None)] == ["sans partenaire"]
    assert [l for l, _ in json_payload_variants({"a": 1}, "J. DOE")] == ["sans partenaire"]


def test_json_payload_variants_never_aliases_the_base():
    from custom_components.tenup.api import json_payload_variants

    # Chaque corps doit etre independant: sinon un appelant qui ecrit dans le
    # premier payload modifierait la base sans le savoir.
    base = {"codeClub": "87654321"}
    for _label, payload in json_payload_variants(base, "John DOE (111111111)"):
        payload["injecte"] = 1
    assert base == {"codeClub": "87654321"}
