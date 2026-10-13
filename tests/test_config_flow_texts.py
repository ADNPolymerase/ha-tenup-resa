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


def test_the_dialog_names_the_cookie_to_copy(monkeypatch):
    """The session cookie is HttpOnly since the 2026 rebuild, so no script can

    hand it over: the dialog has to say which row to copy, and where.
    """
    import json
    from pathlib import Path

    texts = json.loads(
        (Path(__file__).parent.parent / "custom_components/tenup/translations/fr.json")
        .read_text(encoding="utf-8")
    )
    for name in ("cookie", "reauth_confirm", "reconfigure"):
        description = texts["config"]["step"][name]["description"]
        assert "SHARED_SESSION_JAVA" in description, name
        assert "Cookies" in description, name
        assert "{bookmarklet}" not in description, name


def test_the_first_step_points_at_the_club_grid(monkeypatch):
    """The shared cookie only exists inside the reservation area."""
    values = make_flow(monkeypatch=monkeypatch)._placeholders()
    assert values["club_url"] == "https://tenup.fft.fr/club/87654321/reservations"


def test_the_grid_link_follows_each_users_own_club(monkeypatch):
    """Two installs, two clubs, two links: the code comes from the entry."""
    urls = set()
    for code in ("87654321", "12345678"):
        flow = make_flow(monkeypatch=monkeypatch)
        flow._club_code = code
        url = flow._placeholders()["club_url"]
        assert url == f"https://tenup.fft.fr/club/{code}/reservations", code
        urls.add(url)
    assert len(urls) == 2


def test_no_club_code_stays_on_the_site(monkeypatch):
    """Never build a /club/None/ address."""
    flow = make_flow(monkeypatch=monkeypatch)
    flow._club_code = None
    assert flow._placeholders()["club_url"] == "https://tenup.fft.fr"


