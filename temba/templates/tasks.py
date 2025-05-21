import logging

import requests

from temba.channels.models import Channel
from temba.utils.crons import cron_task

logger = logging.getLogger(__name__)


@cron_task()
def refresh_templates():
    """
    Runs across all channels that have connected FB accounts and syncs the templates which are active.
    """

    num_refreshed, num_errored = 0, 0

    # get all active channels for types that use templates
    channel_types = [t.code for t in Channel.get_types() if t.template_type]
    channels = Channel.objects.filter(
        is_active=True, channel_type__in=channel_types, org__is_active=True, org__is_suspended=False
    )

    for channel in channels:
        try:
            channel.refresh_templates()
            num_refreshed += 1
        except requests.RequestException:
            num_errored += 1
        except Exception as e:
            logger.error(f"Error refreshing whatsapp templates: {str(e)}", exc_info=True)

    return {"refreshed": num_refreshed, "errored": num_errored}
