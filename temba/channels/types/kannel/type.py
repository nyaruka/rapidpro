from django.utils.translation import gettext_lazy as _

from temba.channels.types.kannel.views import ClaimView
from temba.contacts.models import URN

from ...models import ChannelType, ConfigUI


class KannelType(ChannelType):
    """
    An Kannel channel (http://www.kannel.org/)
    """

    code = "KN"
    name = "Kannel"
    category = ChannelType.Category.PHONE

    schemes = [URN.TEL_SCHEME]

    claim_blurb = _(
        "Connect your %(link)s instance, we'll walk you through the steps necessary to get your SMSC connection "
        "working in a few minutes."
    ) % {"link": '<a target="_blank" href="http://www.kannel.org/">Kannel</a>'}
    claim_view = ClaimView

    config_ui = ConfigUI()  # has own template
