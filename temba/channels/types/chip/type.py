from temba.contacts.models import URN

from ...models import ChannelType
from .views import ClaimView


class ChipType(ChannelType):
    """
    A chip webchat channel
    """

    code = "CHP"
    name = "Chip"
    slug = "chip"
    category = ChannelType.Category.SOCIAL_MEDIA

    schemes = [URN.WEBCHAT_SCHEME]
    courier_url = r"^chp/(?P<uuid>[a-z0-9\-]+)/(?P<action>receive)$"

    claim_blurb = "Web chat!"
    claim_view = ClaimView

    def is_available_to(self, org, user):
        available = user.is_staff and not org.channels.filter(channel_type=self.code, is_active=True).exists()

        return available, available

    def is_recommended_to(self, org, user):
        return False
