"""The Lovelace resource that loads the bundled Ten'Up card.

The card used to be a separate HACS repository. It now ships with the
integration, which serves it and keeps exactly one resource pointing at it.
"""
import asyncio
import json
from pathlib import Path

from custom_components.tenup import frontend

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "tenup"
NEW_URL = "/tenup_frontend/ha-tenup-card.js?v=9.9.9"
OTHER = {"id": "1", "res_type": "module", "url": "/hacsfiles/other-card/other-card.js"}
# What HACS created while the card was installed on its own.
STANDALONE = "/hacsfiles/ha-tenup-resa-card/ha-tenup-card.js"


class FakeResources:
    """Mimics Lovelace's lazily loaded resource collection."""

    def __init__(self, stored, loaded=False):
        self._stored = [dict(item) for item in stored]
        self._items = [dict(item) for item in stored] if loaded else []
        self.loaded = loaded
        self.load_calls = 0
        self._next = 100

    async def async_load(self):
        self.load_calls += 1
        self._items = [dict(item) for item in self._stored]

    def async_items(self):
        return self._items

    async def async_create_item(self, data):
        self._next += 1
        self._items.append({"id": str(self._next), **data})

    async def async_update_item(self, item_id, data):
        for item in self._items:
            if item["id"] == item_id:
                item.update(data)

    async def async_delete_item(self, item_id):
        self._items = [item for item in self._items if item["id"] != item_id]

    def urls(self):
        return sorted(item["url"] for item in self._items)


def reconcile(resources):
    return asyncio.run(frontend.async_reconcile_card_resource(resources, NEW_URL))


def test_the_resource_is_added_once():
    resources = FakeResources([OTHER])
    reconcile(resources)
    assert resources.urls() == sorted([OTHER["url"], NEW_URL])


def test_a_lazy_collection_is_loaded_before_it_is_read():
    """Read unloaded it looks empty, and a copy would be added on every restart."""
    resources = FakeResources([OTHER, {"id": "2", "res_type": "module", "url": NEW_URL}])
    reconcile(resources)
    assert resources.load_calls == 1
    assert resources.urls() == sorted([OTHER["url"], NEW_URL])


def test_restarting_changes_nothing():
    resources = FakeResources([OTHER])
    reconcile(resources)
    reconcile(resources)
    assert resources.urls().count(NEW_URL) == 1


def test_an_update_rewrites_the_version_in_place():
    old = {"id": "7", "res_type": "module", "url": "/tenup_frontend/ha-tenup-card.js?v=1.1.0"}
    resources = FakeResources([OTHER, old], loaded=True)
    reconcile(resources)
    by_url = {item["url"]: item["id"] for item in resources.async_items()}
    assert by_url.get(NEW_URL) == "7", "the resource was replaced instead of updated"
    assert len(resources.async_items()) == 2


def test_the_standalone_card_resource_is_removed():
    """Two copies of the bundle in one page fight over the same custom elements."""
    resources = FakeResources(
        [OTHER, {"id": "2", "res_type": "module", "url": f"{STANDALONE}?hacstag=123"}],
        loaded=True,
    )
    removed = reconcile(resources)
    assert resources.urls() == sorted([OTHER["url"], NEW_URL])
    assert removed == [f"{STANDALONE}?hacstag=123"]


def test_duplicates_of_our_own_resource_are_removed():
    resources = FakeResources(
        [
            OTHER,
            {"id": "4", "res_type": "module", "url": NEW_URL},
            {"id": "5", "res_type": "module", "url": NEW_URL},
            {"id": "6", "res_type": "module", "url": "/local/ha-tenup-card.js"},
        ],
        loaded=True,
    )
    removed = reconcile(resources)
    assert resources.urls() == sorted([OTHER["url"], NEW_URL])
    assert len(removed) == 2


def test_unrelated_resources_are_left_alone():
    similar = {"id": "9", "res_type": "module", "url": "/local/ha-tenup-card-extra.js"}
    resources = FakeResources([OTHER, similar], loaded=True)
    reconcile(resources)
    assert similar["url"] in resources.urls()
    assert OTHER["url"] in resources.urls()


# ------------------------------------------------------------------- packaging
def test_the_bundle_ships_where_it_is_served_from():
    assert (COMPONENT / frontend.CARD_FILENAME).is_file()


def test_the_url_carries_the_version():
    assert frontend.card_url("1.1.0") == "/tenup_frontend/ha-tenup-card.js?v=1.1.0"


def test_an_unknown_version_still_gives_a_usable_url():
    assert frontend.card_url(None).endswith("?v=0")


def test_the_manifest_declares_what_the_card_needs():
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    assert "http" in manifest["dependencies"]
    assert "lovelace" in manifest["after_dependencies"]


def test_the_card_and_the_integration_carry_the_same_version():
    """They ship together: a mismatch would only ever be an oversight."""
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    bundle = (COMPONENT / frontend.CARD_FILENAME).read_text()
    assert f'const CARD_VERSION = "{manifest["version"]}";' in bundle
