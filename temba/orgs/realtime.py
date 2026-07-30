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
