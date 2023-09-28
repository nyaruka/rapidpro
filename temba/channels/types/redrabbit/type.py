from django.utils.translation import gettext_lazy as _

from temba.channels.views import AuthenticatedExternalClaimView
from temba.contacts.models import URN

from ...models import ChannelType


class RedRabbitType(ChannelType):
    """
    A RedRabbit channel (http://www.redrabbitsms.com/)
    """

    code = "RR"
    name = "Red Rabbit"
    category = ChannelType.Category.PHONE

    schemes = [URN.TEL_SCHEME]

    claim_blurb = _("Easily add a two way number you have configured with %(link)s using their APIs.") % {
        "link": '<a target="_blank" href="http://www.redrabbitsms.com/">Red Rabbit</a>'
    }

    claim_view = AuthenticatedExternalClaimView

    def is_available_to(self, org, user):
        return False, False  # Hidden since it is MT only
