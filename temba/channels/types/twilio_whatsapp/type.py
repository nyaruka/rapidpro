from django.urls import re_path
from django.utils.translation import gettext_lazy as _

from temba.contacts.models import URN
from temba.utils.twilio.views import UpdateCredentials

from ...models import ChannelType
from .views import ClaimView


class TwilioWhatsappType(ChannelType):
    """
    An Twilio channel
    """

    code = "TWA"
    category = ChannelType.Category.SOCIAL_MEDIA

    extra_links = [dict(label=_("Twilio Credentials"), view_name="channels.types.twilio_whatsapp.update_credentials")]

    courier_url = r"^twa/(?P<uuid>[a-z0-9\-]+)/(?P<action>receive|status)$"

    name = "Twilio WhatsApp"
    icon = "icon-whatsapp"

    claim_blurb = _(
        "If you have a %(link)s number, you can connect it to communicate with your WhatsApp contacts."
    ) % {"link": '<a href="https://www.twilio.com/whatsapp/">Twilio WhatsApp</a>'}

    claim_view = ClaimView

    schemes = [URN.WHATSAPP_SCHEME]
    max_length = 1600

    configuration_blurb = _(
        "To finish configuring your Twilio WhatsApp connection you'll need to add the following URL in your Twilio "
        "Inbound Settings. Check the Twilio WhatsApp documentation for more information."
    )

    configuration_urls = (
        dict(
            label=_("Request URL"),
            url="https://{{ channel.callback_domain }}{% url 'courier.twa' channel.uuid 'receive' %}",
            description=_(
                "This endpoint should be called by Twilio when new messages are received by your Twilio WhatsApp "
                "number."
            ),
        ),
    )

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

    def get_error_ref_url(self, channel, code: str) -> str:
        return f"https://www.twilio.com/docs/api/errors/{code}"

    def get_urls(self):
        return [
            self.get_claim_url(),
            re_path(
                r"^(?P<uuid>[a-z0-9\-]+)/update_credentials$", UpdateCredentials.as_view(), name="update_credentials"
            ),
        ]
