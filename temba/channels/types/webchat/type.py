from django.utils.translation import gettext_lazy as _

from temba.contacts.models import URN

from ...models import ChannelType, ConfigUI
from .views import ClaimView


class WebChatType(ChannelType):
    """
    A WebChat channel which lets visitors on a website chat via an embedded widget.
    """

    code = "WCH"
    name = "WebChat"
    category = ChannelType.Category.SOCIAL_MEDIA

    schemes = [URN.WEBCHAT_SCHEME]

    claim_blurb = _("Chat with visitors on your website via an embedded chat widget.")
    claim_view = ClaimView

    config_ui = ConfigUI()  # has own template

    def is_available_to(self, org, user):
        available = user.is_staff

        return available, available

    def is_recommended_to(self, org, user):
        return False
