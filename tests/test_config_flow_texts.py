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


def make_flow(language="fr", url="http://homeassistant.local:8123", monkeypatch=None):
    flow = cf.TenupConfigFlow()
    flow._club_code = "87654321"
    flow._club_name = "DEMO"
    flow.hass = SimpleNamespace(config=SimpleNamespace(language=language))
    monkeypatch.setattr(cf, "get_url", lambda hass: url)
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


def test_the_page_link_is_absolute(monkeypatch):
    """A relative path is not turned into a link by the frontend."""
    values = make_flow(monkeypatch=monkeypatch)._placeholders()
    assert values["bookmarklet_url"].startswith("http")
    assert values["bookmarklet_url"].endswith("/api/tenup/bookmarklet")


def test_the_bookmarklet_is_shown_in_the_dialog(monkeypatch):
    values = make_flow(monkeypatch=monkeypatch)._placeholders()
    assert values["bookmarklet"].startswith("javascript:(function()")
    assert "SHARED_SESSION_DRUPAL" in values["bookmarklet"]


def test_the_bookmarklet_follows_the_home_assistant_language(monkeypatch):
    fr = make_flow(language="fr", monkeypatch=monkeypatch)._placeholders()["bookmarklet"]
    en = make_flow(language="en", monkeypatch=monkeypatch)._placeholders()["bookmarklet"]
    assert "Connectez-vous" in fr and "Connectez-vous" not in en
    assert "Log in on" in en and "Log in on" not in fr


def test_a_missing_home_assistant_url_does_not_break_the_dialog(monkeypatch):
    def boom(hass):
        raise cf.NoURLAvailableError
    monkeypatch.setattr(cf, "get_url", boom)
    flow = cf.TenupConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="fr"))
    values = flow._placeholders()
    assert values["bookmarklet_url"] == "/api/tenup/bookmarklet"
    assert values["bookmarklet"].startswith("javascript:")
