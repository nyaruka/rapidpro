from __future__ import unicode_literals, absolute_import

from django.utils.translation import ugettext_lazy as _

from temba.channels.types.clickatell.views import ClaimView
from temba.contacts.models import TEL_SCHEME
from ...models import ChannelType


class ClickatellType(ChannelType):
    """
    A Clickatell channel (https://clickatell.com/)
    """

    code = 'CT'
    category = ChannelType.Category.PHONE

    name = "Clickatell"
    icon = "icon-channel-clickatell"

    claim_blurb = _("""Connect your <a href="http://clickatell.com/" target="_blank">Clickatell</a> number, we'll walk you
                           through the steps necessary to get your Clickatell connection working in a few minutes.""")

    configuration_blurb = _(
        """
        <h4>
        To finish configuring your Clickatell connection you'll need to set the following callback URLs on the
        Clickatell website for your integration.
        </h4>

        <h4>Reply Callback</h4>

        <p>
        You can set the callback URL on your Clickatell account by managing your integration, then setting your reply
        callback under "Two Way Settings" to HTTP POST and your target address to the URL below.
        (leave username and password blank)
        </p>

        <code>https://{{ channel.callback_domain }}{% url 'courier.ct' channel.uuid 'receive' %}</code>

        <hr>

        <h4>Delivery Notifications</h4>

        <p>
        You can set the delivery notification URL on your Clickatell account by managing your integration,
        then setting your delivery notification URL under "Settings" to HTTP POST and your target address
        to the URL below. (leave username and password blank)
        </p>

        <code>https://{{ channel.callback_domain }}{% url 'courier.ct' channel.uuid 'status' %}</code>
        <hr>
        """
    )

    claim_view = ClaimView

    schemes = [TEL_SCHEME]
    max_length = 420
    attachment_support = False

    def send(self, channel, msg, text):  # pragma: no cover
        raise Exception("Sending Clickatell messages is only possible via Courier")
