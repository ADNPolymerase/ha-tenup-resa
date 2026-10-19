"""Nothing may call a client method that no longer exists.

The 2.0.0 rewrite dropped ``async_search_clubs`` from the client and left the
config flow calling it, so searching a club by name raised an AttributeError on
the very first screen of the setup. A hundred and thirty tests went green: they
all built a client and called it directly, and not one walked the path a new
user walks. This reads the integration's own source instead, and fails on any
client attribute the code uses but the class does not have.
"""
import ast
from pathlib import Path

from custom_components.tenup.api import TenupClient

PACKAGE = Path(TenupClient.__module__.replace(".", "/")).parent
ROOT = Path(__file__).resolve().parent.parent / PACKAGE

# Names the integration gives a client. ``self._client`` / ``self.client`` are
# attributes, matched on their own attribute name below.
CLIENT_NAMES = {"client", "_client", "TenupClient"}


def client_attributes():
    """Every attribute the integration reads on something that is a client."""
    for path in sorted(ROOT.glob("*.py")):
        if path.name == "api.py":
            continue  # the class itself, where the methods are defined
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            target = node.value
            name = (
                target.id
                if isinstance(target, ast.Name)
                else target.attr
                if isinstance(target, ast.Attribute)
                else None
            )
            if name in CLIENT_NAMES:
                yield path.name, node.lineno, node.attr


def test_every_client_attribute_the_integration_uses_exists():
    missing = [
        (f, line, attr)
        for f, line, attr in client_attributes()
        if not hasattr(TenupClient, attr)
    ]
    assert not missing, missing


def test_the_config_flow_can_still_search_a_club_by_name():
    """The README's first step, and the only one that needs no session."""
    assert hasattr(TenupClient, "async_search_clubs")


def test_the_check_would_have_caught_the_rewrite():
    """A method dropped from the client has to make the check fail."""
    uses = {attr for _, _, attr in client_attributes()}
    assert "async_search_clubs" in uses
    assert "async_validate" in uses
    assert not {"async_search_clubs", "async_validate"} - set(dir(TenupClient))
