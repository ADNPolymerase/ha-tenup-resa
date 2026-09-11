"""The install page is what replaces the trip through the developer tools."""
import re

from custom_components.tenup.http import BOOKMARKLET_URL, render_page


def test_the_link_is_a_real_javascript_anchor():
    """It must stay draggable to the bookmarks bar: that is the whole point."""
    page = render_page("fr-FR,fr;q=0.9")
    assert re.search(r'<a class="bm" href="javascript:\(function\(\)', page)


def test_the_bookmarklet_reads_the_shared_cookie():
    page = render_page("fr")
    assert "SHARED_SESSION_DRUPAL=" in page
    assert "document.cookie.match" in page


def test_french_browser_gets_french():
    page = render_page("fr-FR,fr;q=0.9,en;q=0.8")
    assert 'lang="fr"' in page
    assert "Glissez ce bouton" in page


def test_other_browsers_get_english():
    for header in ("en-GB,en;q=0.9", "de-DE", ""):
        page = render_page(header)
        assert 'lang="en"' in page, header
        assert "Drag this button" in page, header


def test_a_french_second_preference_is_honoured():
    """Accept-Language often leads with another locale before fr."""
    page = render_page("en-US,fr;q=0.9")
    assert 'lang="fr"' in page


def test_the_page_holds_no_session_and_no_user_data():
    """It is served without authentication, so it must be pure documentation."""
    page = render_page("fr")
    for leak in ("SSESS7ba", "datadome", "aae6fe4e", "token", "password"):
        assert leak not in page, leak


def test_the_url_stays_under_the_integration_namespace():
    assert BOOKMARKLET_URL == "/api/tenup/bookmarklet"


def test_quotes_in_the_href_are_escaped():
    """An unescaped double quote would cut the href short and break the drag."""
    page = render_page("fr")
    href = re.search(r'<a class="bm" href="([^"]+)"', page).group(1)
    assert "&quot;" in href
    assert href.endswith("})()")
