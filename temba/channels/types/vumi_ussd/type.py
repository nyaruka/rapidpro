from __future__ import unicode_literals, absolute_import

import six

from django.utils.translation import ugettext_lazy as _

from temba.channels.models import Channel, ChannelType
from temba.channels.types.vumi_ussd.views import ClaimView
from temba.contacts.models import TEL_SCHEME


class VumiUSSDType(ChannelType):
    """
    A Vumi USSD channel
    """

    code = 'VMU'
    category = ChannelType.Category.USSD

    name = "Vumi USSD"
    slug = 'vumi_ussd'

    claim_blurb = _("""Easily connect your <a href="http://go.vumi.org/">Vumi</a> account to take advantage of session based messaging across USSD transports.""")

    configuration_blurb = _(
        """
        <h4>
        To finish configuring your Vumi connection you'll need to set the following parameters on your Vumi conversation:
        </h4>

        <div class ="clearfix">
            <div class="config-value">
                <div class="name">
                Conversation Key:
                </div>
                <div class="value">
                {{ channel.config_json.conversation_key }}
                </div>
            </div>
            <div class="config-value">
                <div class="name">
                Account Key:
                </div>
                <div class="value">
                {{ channel.config_json.account_key }}
                </div>
            </div>
        </div>
        <div class="clearfix"></div>

        <hr/>

        <h4>API Token</h4>

        <p>
        This token is used to authenticate with your Vumi account, set it by editing the "Content" page on your conversation.
        </p>

        <code>{{ channel.config_json.access_token }}</code>

        <hr/>

        <h4>Push Message URL</h4>

        <p>
        This endpoint will be called by Vumi when new messages are received to your number.
        </p>

        <code>https://{{ channel.callback_domain }}{% url 'courier.vm' channel.uuid 'receive' %}</code>

        <hr/>

        <h4>Push Event URL</h4>

        <p>
        This endpoint will be called by Vumi when sent messages are sent or delivered.
        </p>

        <code>https://{{ channel.callback_domain }}{% url 'courier.vm' channel.uuid 'event' %}</code>
        <hr/>
        """
    )

    claim_view = ClaimView

    schemes = [TEL_SCHEME]
    max_length = 182

    is_ussd = True

    def is_available_to(self, user):
        org = user.get_org()
        return org.timezone and six.text_type(org.timezone) in ['Africa/Johannesburg']

    def send(self, channel, msg, text):
        # use regular Vumi channel sending
        return Channel.get_type_from_code('VM').send(channel, msg, text)
