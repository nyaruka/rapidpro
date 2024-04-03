import base64

import requests

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from temba.channels.types.twilio.type import TwilioType
from temba.channels.types.twilio.views import UpdateForm
from temba.contacts.models import URN
from temba.request_logs.models import HTTPLog
from temba.templates.whatsapp import extract_params

from ...models import Channel, ChannelType, ConfigUI
from .views import ClaimView


class TwilioWhatsappType(ChannelType):
    """
    An Twilio channel
    """

    SESSION_ACCOUNT_SID = TwilioType.SESSION_ACCOUNT_SID
    SESSION_AUTH_TOKEN = TwilioType.SESSION_AUTH_TOKEN

    code = "TWA"
    name = "Twilio WhatsApp"
    category = ChannelType.Category.SOCIAL_MEDIA

    unique_addresses = True

    courier_url = r"^twa/(?P<uuid>[a-z0-9\-]+)/(?P<action>receive|status)$"
    schemes = [URN.WHATSAPP_SCHEME]
    redact_request_keys = (
        "FromCity",
        "FromState",
        "FromZip",
        "ToCity",
        "ToState",
        "ToZip",
        "CalledCity",
        "CalledState",
        "CalledZip",
    )

    claim_blurb = _("If you have a %(link)s number, you can connect it to communicate with your WhatsApp contacts.") % {
        "link": '<a target="_blank" href="https://www.twilio.com/whatsapp/">Twilio WhatsApp</a>'
    }

    claim_view = ClaimView
    update_form = UpdateForm

    config_ui = ConfigUI(
        blurb=_(
            "To finish configuring this channel, you'll need to add the following URL in your Twilio "
            "Inbound Settings. Check the Twilio WhatsApp documentation for more information."
        ),
        endpoints=[
            ConfigUI.Endpoint(
                courier="receive",
                label=_("Request URL"),
                help=_("This endpoint should be called by Twilio when new messages are received by your number."),
            ),
        ],
    )

    def get_error_ref_url(self, channel, code: str) -> str:
        return f"https://www.twilio.com/docs/api/errors/{code}"

    def check_credentials(self, config: dict) -> bool:
        return TwilioType().check_credentials(config)

    def fetch_templates(self, channel) -> list:
        url = "https://content.twilio.com/v1/Content"
        credentials_base64 = base64.b64encode(
            f"{channel.config[Channel.CONFIG_ACCOUNT_SID]}:{channel.config[Channel.CONFIG_AUTH_TOKEN]}".encode()
        ).decode()

        headers = {"Authorization": f"Basic {credentials_base64}"}

        twilio_templates = []

        while url:
            start = timezone.now()
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                HTTPLog.from_response(
                    HTTPLog.WHATSAPP_TEMPLATES_SYNCED, response, start, timezone.now(), channel=channel
                )

                twilio_templates.extend(response.json()["contents"])
                url = response.json().get("meta", {}).get("next_page_url", None)
            except Exception as e:
                HTTPLog.from_exception(HTTPLog.WHATSAPP_TEMPLATES_SYNCED, e, start, channel=channel)
                raise e

        templates = []

        for temp in twilio_templates:
            approval_url = temp["links"]["approval_fetch"]
            approval_start = timezone.now()
            try:
                response = requests.get(approval_url, headers=headers)
                response.raise_for_status()
                HTTPLog.from_response(
                    HTTPLog.WHATSAPP_TEMPLATES_SYNCED, response, approval_start, timezone.now(), channel=channel
                )
                status = response.json()["whatsapp"]["status"]
                category = response.json()["whatsapp"]["category"]
            except Exception as e:
                HTTPLog.from_exception(HTTPLog.WHATSAPP_TEMPLATES_SYNCED, e, approval_start, channel=channel)
                status = "unsubmitted"
                category = ""

            components = []

            for content_type in temp["types"]:
                buttons = []
                if "actions" in temp["types"][content_type]:
                    for action in temp["types"][content_type]["actions"]:
                        if content_type == "twilio/quick-reply":
                            buttons.append({"type": "quick_reply", "text": action["title"]})
                        elif content_type == "twilio/call-to-action":
                            if action["type"].upper() == "URL":
                                buttons.append({"type": action["type"], "text": action["title"], "url": action["url"]})
                            elif action["type"].upper() == "PHONE_NUMBER":
                                buttons.append(
                                    {"type": action["type"], "text": action["title"], "phone_number": action["phone"]}
                                )

                if "body" in temp["types"][content_type]:
                    components.append({"type": "body", "text": temp["types"][content_type]["body"]})
                if "media" in temp["types"][content_type]:
                    if extract_params(temp["types"][content_type]["media"][0]):
                        components.append({"type": "header", "format": "unknown"})
                if buttons:
                    components.append({"type": "buttons", "buttons": buttons})

            templates.append(
                {
                    "id": temp["sid"],
                    "status": status,
                    "category": category,
                    "language": temp["language"],
                    "name": temp["friendly_name"],
                    "components": components,
                }
            )

        return templates
