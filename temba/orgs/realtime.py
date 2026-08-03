"""
Publishing of workspace-wide realtime events to the ``org:<org-uuid>`` socket, so that clients can keep their caches of
asset names fresh without refetching or reloading.

Phase one deliberately only publishes renames of flows and groups (see `AssetNameMixin`) as those are the references
which appear most often in flow definitions. The other asset types resolvable via the internal assets endpoint
(channels, contacts, labels, LLMs, opt-ins, templates, topics, fields, globals and users) don't publish, so clients
still fall back to refetching or a page reload to see those renames.
"""

import logging

from django.db import transaction

logger = logging.getLogger(__name__)


def publish_asset_changed(org, asset_type: str, uuid, name: str):
    """Publishes a committed workspace asset name change, best effort."""
    event = {
        "type": "asset_changed",
        "asset": {"type": asset_type, "uuid": str(uuid), "name": name},
    }
    transaction.on_commit(lambda: _publish_org_event(org, event))


def _publish_org_event(org, event: dict):
    # Keep realtime delivery outside the saving transaction and non-fatal: the
    # cache will recover from a missed publication on its next socket refresh.
    from temba.mailroom import get_client

    try:
        get_client().org_publish(org, event)
    except Exception:
        logger.exception("error publishing workspace event to mailroom")


class AssetNameMixin:
    """
    Mixin for models whose renames are published as `asset_changed` events. Must be listed before the model base classes
    so that our `save` runs, and `asset_type` must be set to the type name used in flow definitions.

    We hook into saving rather than the handful of places which rename (the update modals, flow imports, the API v2
    groups endpoint) so that no rename path can be missed, and we track the loaded name so that detecting a rename never
    costs an extra query.
    """

    asset_type = None

    @classmethod
    def from_db(cls, db, field_names, values):
        obj = super().from_db(db, field_names, values)

        if "name" in field_names:  # won't be if name was deferred, in which case we can't detect renames
            obj._loaded_name = obj.name

        return obj

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # if name wasn't written then any in-memory change to it isn't persisted, so there's nothing to publish and we
        # mustn't start tracking it either (Model.save is keyword only so update_fields is always in kwargs if given)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "name" not in update_fields:
            return

        loaded_name = getattr(self, "_loaded_name", None)

        # don't publish for objects we just created, or ones being deactivated as release() renames to a tombstone.
        # is_active is checked last as it's the only part which can cost a query, if it was deferred when loading.
        if loaded_name is not None and loaded_name != self.name and self.is_active:
            publish_asset_changed(self.org, self.asset_type, self.uuid, self.name)

        self._loaded_name = self.name
