import base64
import logging

import requests

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from temba.channels.models import Channel, ChannelType, ConfigUI
from temba.channels.types.turn.views import ClaimView
from temba.contacts.models import URN
from temba.request_logs.models import HTTPLog

CONFIG_FB_BUSINESS_ID = "fb_business_id"
CONFIG_FB_ACCESS_TOKEN = "fb_access_token"
CONFIG_FB_NAMESPACE = "fb_namespace"
CONFIG_FB_TEMPLATE_LIST_DOMAIN = "fb_template_list_domain"
CONFIG_FB_TEMPLATE_API_VERSION = "fb_template_list_domain_api_version"

TEMPLATE_LIST_URL = "https://%s/%s/%s/message_templates"

logger = logging.getLogger(__name__)


class TurnType(ChannelType):
    """
    A Turn.io WhatsApp Channel Type
    """

    code = "TRN"
    name = "Turn.io WhatsApp"
    category = ChannelType.Category.SOCIAL_MEDIA
    org_feature = "trn_channel_type"

    unique_addresses = True

    courier_url = r"^trn/(?P<uuid>[a-z0-9\-]+)/(?P<action>receive)$"
    schemes = [URN.WHATSAPP_SCHEME]
    template_type = "whatsapp"

    claim_blurb = _(
        "If you have an enterprise Turn.io WhatsApp account, you can connect it to communicate with your contacts"
    )
    claim_view = ClaimView

    config_ui = ConfigUI(
        blurb=_("To finish configuring this channel, you'll need Turn.io to use the following callback URL."),
        endpoints=[
            ConfigUI.Endpoint(
                courier="receive",
                label=_("Receive URL"),
                help=_("This URL should be called by Turn.io when new messages are received."),
            ),
        ],
    )

    def fetch_templates(self, channel) -> list:
        # Retrieve the template domain, fallback to the default for channels that have been setup earlier for backwards
        # compatibility
        facebook_template_domain = channel.config.get(CONFIG_FB_TEMPLATE_LIST_DOMAIN, "graph.facebook.com")
        facebook_business_id = channel.config.get(CONFIG_FB_BUSINESS_ID)
        facebook_template_api_version = channel.config.get(CONFIG_FB_TEMPLATE_API_VERSION, "v14.0")
        url = TEMPLATE_LIST_URL % (facebook_template_domain, facebook_template_api_version, facebook_business_id)
        templates = []

        while url:
            start = timezone.now()
            try:
                response = requests.get(
                    url, params={"access_token": channel.config[CONFIG_FB_ACCESS_TOKEN], "limit": 255}
                )
                response.raise_for_status()
                HTTPLog.from_response(
                    HTTPLog.WHATSAPP_TEMPLATES_SYNCED, response, start, timezone.now(), channel=channel
                )

                templates.extend(response.json()["data"])
                url = response.json().get("paging", {}).get("next", None)
            except requests.RequestException as e:
                HTTPLog.from_exception(HTTPLog.WHATSAPP_TEMPLATES_SYNCED, e, start, channel=channel)
                raise e

        return templates

    def get_redact_values(self, channel) -> tuple:
        """
        Gets the values to redact from logs
        """
        credentials_base64 = base64.b64encode(
            f"{channel.config[Channel.CONFIG_USERNAME]}:{channel.config[Channel.CONFIG_PASSWORD]}".encode()
        ).decode()
        return (
            channel.config[CONFIG_FB_ACCESS_TOKEN],
            channel.config[Channel.CONFIG_PASSWORD],
            credentials_base64,
        )
