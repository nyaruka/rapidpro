from django.utils.translation import gettext_lazy as _

from temba.contacts.models import URN

from ...models import ChannelType
from .views import ClaimView


class SlackType(ChannelType):
    """
    A Slack bot channel
    """

    CONFIG_BOT_TOKEN = "bot_token"
    CONFIG_USER_TOKEN = "user_token"
    CONFIG_VERIFICATION_TOKEN = "verification_token"

    code = "SL"
    slug = "slack"
    name = "Slack"
    category = ChannelType.Category.SOCIAL_MEDIA
    schemes = [URN.SLACK_SCHEME]

    courier_url = r"^sl/(?P<uuid>[a-z0-9\-]+)/receive$"

    claim_blurb = _("Add a %(link)s bot to send and receive messages to Slack users, on your slack workspace.") % {
        "link": '<a target="_blank" href="https://slack.com">Slack</a>'
    }

    claim_view = ClaimView
