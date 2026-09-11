"""A page Home Assistant serves itself, to install the Ten'Up bookmarklet.

The bookmarklet has to be a bookmark: a link cannot both navigate to Ten'Up and
run a script there, and a script run from the Home Assistant page would read
Home Assistant's own cookies. Serving the page from here (rather than linking to
GitHub) lets the link stay a real ``javascript:`` anchor, so it can be dragged
straight to the bookmarks bar. Browsers routinely drop that scheme when it is
pasted into a bookmark dialog by hand, and Home Assistant's own markdown strips
it, so dragging is the reliable way.
"""

from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback

BOOKMARKLET_URL = "/api/tenup/bookmarklet"

# Reads the cookie that bridges Ten'Up and its reservation area, copies it, and
# falls back to showing it when the browser refuses clipboard access.
BOOKMARKLET = (
    'javascript:(function(){var m=document.cookie.match('
    '/(?:^|;\\s*)SHARED_SESSION_DRUPAL=([^;]+)/);'
    'if(!m){alert("%(signed_out)s");return}'
    'var v="SHARED_SESSION_DRUPAL="+m[1];'
    'function f(){prompt("%(paste)s",v)}'
    'try{navigator.clipboard.writeText(v).then(function(){alert("%(copied)s")},f)}'
    'catch(e){f()}})()'
)

FR = {
    # Les textes du marque-page restent sans accent: ils partent dans une URL
    # javascript: que le navigateur transporte telle quelle jusqu'au favori.
    "signed_out": "Ouvrez d'abord Reserver dans mon club sur tenup.fft.fr, connectez-vous, puis recliquez ici.",
    "paste": "Collez ceci dans Home Assistant:",
    "copied": "Session copiee. Collez-la dans Home Assistant (Ctrl+V ou Cmd+V).",
    "title": "Marque-page Ten'Up",
    "lead": "\u00c0 installer une seule fois. Ensuite, un clic dessus depuis Ten'Up copie "
            "votre session, et il n'y a plus qu'\u00e0 la coller dans Home Assistant.",
    "drag": "Glissez ce bouton dans votre barre de favoris",
    "label": "Session Ten'Up",
    "hint": "Barre de favoris masqu\u00e9e ? Ctrl+Maj+B (Cmd+Maj+B sur Mac) l'affiche.",
    "manual_title": "Ou cr\u00e9ez-le \u00e0 la main",
    "manual": "Copiez cette ligne comme adresse d'un nouveau favori. Gardez bien le "
              "<code>javascript:</code> du d\u00e9but, que certains navigateurs effacent "
              "au collage.",
    "copy": "Copier la ligne",
    "done": "Copi\u00e9",
    "page_link": "Plus simple encore, [cette page]({url}) vous laisse le glisser "
                 "directement dans votre barre de favoris.",
    "use": "Ensuite, \u00e0 chaque fois",
    "steps": [
        "Sur tenup.fft.fr, connectez-vous et ouvrez <b>R\u00e9server dans mon club</b>.",
        "Cliquez le favori <b>Session Ten'Up</b> : il copie votre session.",
        "Collez-la dans Home Assistant.",
    ],
}
EN = {
    "signed_out": "Open Book at my club on tenup.fft.fr first, log in, then click here again.",
    "paste": "Paste this into Home Assistant:",
    "copied": "Session copied. Paste it into Home Assistant (Ctrl+V or Cmd+V).",
    "title": "Ten'Up bookmarklet",
    "lead": "Install it once. After that, one click on it from Ten'Up copies your "
            "session, and all that is left is pasting it into Home Assistant.",
    "drag": "Drag this button to your bookmarks bar",
    "label": "Ten'Up session",
    "hint": "Bookmarks bar hidden? Ctrl+Shift+B (Cmd+Shift+B on a Mac) shows it.",
    "manual_title": "Or create it by hand",
    "manual": "Copy this line as the address of a new bookmark. Keep the "
              "<code>javascript:</code> prefix, which some browsers drop when it is "
              "pasted.",
    "copy": "Copy the line",
    "done": "Copied",
    "page_link": "Easier still, [this page]({url}) lets you drag it straight to "
                 "your bookmarks bar.",
    "use": "Then, every time",
    "steps": [
        "On tenup.fft.fr, log in and open <b>Book at my club</b>.",
        "Click the <b>Ten'Up session</b> bookmark: it copies your session.",
        "Paste it into Home Assistant.",
    ],
}

_PAGE = """<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>{t[title]}</title><style>
:root {{ color-scheme: light dark; --bg:#f6f7f9; --card:#fff; --fg:#16191d;
  --muted:#5c6873; --line:#dfe3e8; --accent:#03a9f4; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#111417; --card:#1b1f24;
  --fg:#e6edf3; --muted:#9aa7b4; --line:#2b333b; }} }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:16px/1.6
  -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
main {{ max-width:680px; margin:0 auto; padding:32px 20px 64px; }}
h1 {{ font-size:24px; margin:0 0 8px; }}
p.lead {{ color:var(--muted); margin:0 0 28px; }}
section {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
  padding:20px; margin-bottom:18px; }}
h2 {{ font-size:14px; text-transform:uppercase; letter-spacing:.04em;
  color:var(--muted); margin:0 0 14px; }}
a.bm {{ display:inline-block; background:var(--accent); color:#00212e;
  text-decoration:none; font-weight:700; padding:11px 22px; border-radius:8px;
  cursor:grab; }}
a.bm:active {{ cursor:grabbing; }}
p.hint {{ color:var(--muted); font-size:14px; margin:14px 0 0; }}
p.hint code {{ display:inline; padding:1px 5px; font-size:12.5px; }}
code {{ display:block; background:var(--bg); border:1px solid var(--line);
  border-radius:8px; padding:12px; margin:12px 0; font:12.5px/1.5
  ui-monospace,SFMono-Regular,Menlo,monospace; word-break:break-all; }}
button {{ background:transparent; border:1px solid var(--line); color:var(--fg);
  border-radius:8px; padding:8px 14px; font-size:14px; cursor:pointer; }}
ol {{ margin:0; padding-left:22px; }} li {{ margin:6px 0; }}
</style></head><body><main>
<h1>{t[title]}</h1><p class="lead">{t[lead]}</p>
<section><h2>{t[drag]}</h2>
<a class="bm" href="{bm}">{t[label]}</a>
<p class="hint">{t[hint]}</p></section>
<section><h2>{t[manual_title]}</h2><p class="hint">{t[manual]}</p>
<code id="bm">{bm_text}</code>
<button id="c">{t[copy]}</button></section>
<section><h2>{t[use]}</h2><ol>{steps}</ol></section>
</main><script>
document.getElementById("c").onclick=function(){{
  var b=this;navigator.clipboard.writeText(document.getElementById("bm").textContent)
   .then(function(){{b.textContent="{t[done]}"}});}};
</script></body></html>"""


def render_page(language: str) -> str:
    """The install page, in French for a French browser, in English otherwise."""
    french = language.lower().startswith("fr") or ",fr" in language.lower()
    t = FR if french else EN
    bm = BOOKMARKLET % t
    return _PAGE.format(
        lang="fr" if french else "en",
        t=t,
        bm=bm.replace("&", "&amp;").replace('"', "&quot;"),
        bm_text=bm.replace("&", "&amp;").replace("<", "&lt;"),
        steps="".join(f"<li>{s}</li>" for s in t["steps"]),
    )


class TenupBookmarkletView(HomeAssistantView):
    """Serve the install page. Unauthenticated: it holds no user data."""

    url = BOOKMARKLET_URL
    name = "api:tenup:bookmarklet"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        return web.Response(
            text=render_page(request.headers.get("Accept-Language", "")),
            content_type="text/html",
        )


@callback
def async_setup_bookmarklet_page(hass: HomeAssistant) -> None:
    hass.http.register_view(TenupBookmarkletView())
