from __future__ import unicode_literals, absolute_import

import six

from django.utils.translation import ugettext_lazy as _

from temba.channels.types.zenvia.views import ClaimView
from temba.contacts.models import TEL_SCHEME
from temba.channels.models import ChannelType


class ZenviaType(ChannelType):
    """
    An Zenvia channel (https://www.zenvia.com/)
    """

    code = 'ZV'
    category = ChannelType.Category.PHONE

    name = "Zenvia"

    claim_blurb = _("""If you are based in Brazil, you can purchase a short code from <a href="http://www.zenvia.com.br/">Zenvia</a> and connect it in a few simple steps.""")

    configuration_blurb = _(
        """
        <h4>
        To finish configuring your Zenvia connection you'll need to set the following callback URLs on your Zenvia account."
        </h4>

        <div class="clearfix">
            <div class="config-value">
                <div class="name">
                Account:
                </div>
                <div class="value">
                {{ channel.config_json.account }}
                </div>
            </div>
            <div class="config-value">
                <div class="name">
                Code:
                </div>
                <div class="value">
                {{ channel.config_json.code }}
                </div>
            </div>


        </div>

        <div class="clearfix"></div>
        <hr/>

        <h4>Status URL</h4>

        <p>
        To receive delivery and acknowledgement of sent messages, you need to set the status URL
        for your Zenvia account.
        </p>

        <code>https://{{ channel.callback_domain }}{% url 'courier.zv' channel.uuid 'status' %}</code>

        <hr/>

        <h4>Receive URL</h4>

        <p>
        To receive incoming messages, you need to set the receive URL for your Zenvia account.
        </p>

        <code>https://{{ channel.callback_domain }}{% url 'courier.zv' channel.uuid 'receive' %}</code>

        <hr/>

        """
    )

    claim_view = ClaimView

    schemes = [TEL_SCHEME]
    max_length = 150

    attachment_support = False

    def is_available_to(self, user):
        org = user.get_org()
        return org.timezone and six.text_type(org.timezone) in ['America/Sao_Paulo']

    def send(self, channel, msg, text):  # pragma: no cover
        raise Exception("Sending Zenvia messages is only possible via Courier")
