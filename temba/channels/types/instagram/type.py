import requests

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from temba.contacts.models import URN

from ...models import Channel, ChannelType
from .views import ClaimView


class InstagramType(ChannelType):
    """
    A Instagram channel
    """

    code = "IG"
    name = "Instagram"
    category = ChannelType.Category.SOCIAL_MEDIA

    unique_addresses = True
    matching_addresses_updates = True

    courier_url = r"^ig/receive"
    schemes = [URN.INSTAGRAM_SCHEME]

    claim_blurb = _("Add an %(link)s bot to send and receive messages on behalf of a business Instagram account.") % {
        "link": '<a target="_blank" href="http://instagram.com">Instagram</a>',
    }
    claim_view = ClaimView

    menu_items = [
        dict(label=_("Reconnect Business Account"), view_name="channels.types.instagram.claim", obj_view=False)
    ]

    def deactivate(self, channel):
        config = channel.config
        requests.delete(
            f"https://graph.facebook.com/v18.0/{channel.address}/subscribed_apps",
            params={"access_token": config[Channel.CONFIG_AUTH_TOKEN]},
        )

    def get_redact_values(self, channel) -> tuple:  # pragma: needs cover
        """
        Gets the values to redact from logs
        """
        return (settings.FACEBOOK_APPLICATION_SECRET, settings.FACEBOOK_WEBHOOK_SECRET)

    def get_error_ref_url(self, channel, code: str) -> str:
        return "https://developers.facebook.com/docs/instagram-api/reference/error-codes"
