"""Every {placeholder} a dialog uses must be one the flow actually provides.

A missing one makes Home Assistant render the description wrong with no error,
and a link written as a relative path is not rendered as a link at all.
"""
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from custom_components.tenup import config_flow as cf

TRANSLATIONS = Path(cf.__file__).parent
FILES = ["strings.json", "translations/fr.json", "translations/en.json"]


def descriptions():
    for name in FILES:
        data = json.loads((TRANSLATIONS / name).read_text(encoding="utf-8"))
        for step, body in data["config"]["step"].items():
            yield name, step, body.get("description", "")


def make_flow(language="fr", monkeypatch=None):
    flow = cf.TenupConfigFlow()
    flow._club_code = "87654321"
    flow._club_name = "DEMO"
    flow.hass = SimpleNamespace(config=SimpleNamespace(language=language))
    return flow


def test_every_placeholder_used_is_provided(monkeypatch):
    provided = set(make_flow(monkeypatch=monkeypatch)._placeholders())
    for name, step, text in descriptions():
        used = set(re.findall(r"\{(\w+)\}", text))
        assert used <= provided, (name, step, used - provided)


def test_every_description_renders(monkeypatch):
    """The real proof: formatting must not raise, and must leave nothing unfilled."""
    values = make_flow(monkeypatch=monkeypatch)._placeholders()
    for name, step, text in descriptions():
        rendered = text.format(**values)  # raises on an unknown placeholder
        assert "{club}" not in rendered and "{bookmarklet}" not in rendered, (name, step)
        if "bookmarklet" in text:
            assert "javascript:(function()" in rendered, (name, step)


def test_no_link_points_back_at_home_assistant(monkeypatch):
    """A same-origin link is swallowed by the frontend router, which lands the
    user on their default dashboard instead of the page."""
    for name, step, text in descriptions():
        assert "/api/tenup/" not in text, (name, step)
        assert "install_page" not in text, (name, step)


def test_the_bookmarklet_is_shown_in_the_dialog(monkeypatch):
    values = make_flow(monkeypatch=monkeypatch)._placeholders()
    assert values["bookmarklet"].startswith("javascript:(function()")
    assert "SHARED_SESSION_DRUPAL" in values["bookmarklet"]


def test_the_bookmarklet_follows_the_home_assistant_language(monkeypatch):
    fr = make_flow(language="fr", monkeypatch=monkeypatch)._placeholders()["bookmarklet"]
    en = make_flow(language="en", monkeypatch=monkeypatch)._placeholders()["bookmarklet"]
    assert "Reserver dans mon club" in fr and "Reserver dans mon club" not in en
    assert "Book at my club" in en and "Book at my club" not in fr


def test_the_first_step_points_at_the_club_grid(monkeypatch):
    """The shared cookie only exists inside the reservation area."""
    values = make_flow(monkeypatch=monkeypatch)._placeholders()
    assert values["club_url"].startswith("https://tenup.fft.fr/club/87654321/reservations/")
    assert values["club_url"][-8:].isdigit()


def test_the_grid_link_follows_each_users_own_club(monkeypatch):
    """Two installs, two clubs, two links: the code comes from the entry."""
    urls = set()
    for code in ("87654321", "12345678"):
        flow = make_flow(monkeypatch=monkeypatch)
        flow._club_code = code
        url = flow._placeholders()["club_url"]
        assert f"/club/{code}/reservations/" in url, code
        urls.add(url)
    assert len(urls) == 2


def test_no_club_code_stays_on_the_site(monkeypatch):
    """Never build a /club/None/ address."""
    flow = make_flow(monkeypatch=monkeypatch)
    flow._club_code = None
    assert flow._placeholders()["club_url"] == "https://tenup.fft.fr"


def test_the_bookmarklet_says_where_to_be(monkeypatch):
    """Its failure message is the only guidance a user gets on the wrong page."""
    fr = make_flow(monkeypatch=monkeypatch)._placeholders()["bookmarklet"]
    assert "Reserver dans mon club" in fr


