from __future__ import unicode_literals, absolute_import

import json
import requests
import six
import time

from django.utils.translation import ugettext_lazy as _
from temba.contacts.models import LINE_SCHEME
from temba.msgs.models import WIRED
from temba.utils.http import HttpEvent, http_headers
from .views import ClaimView
from ...models import Channel, ChannelType, SendException


class LineType(ChannelType):
    """
    A LINE channel (https://line.me/)
    """
    code = 'LN'
    category = ChannelType.Category.SOCIAL_MEDIA

    name = "LINE"
    icon = 'icon-line'

    claim_blurb = _("""Add a <a href="https://line.me">LINE</a> bot to send and receive messages to LINE users
                for free. Your users will need an Android, Windows or iOS device and a LINE account to send
                and receive messages.""")

    configuration_blurb = _(
        """
        <h4>
        To finish the configuration of Line channel you'll need to set the following callback URL in the Line Bot settings page, following the steps below:
        </h4>

        <div class="info">
            <p>
                <ol class="line-steps"
                    <li>
                        Configure "Callback URL" in the channel page (the same page which get the information Channel Secret and Channel Access Token) by clicking on the "Edit" button, filling the field "webhook URL" and pressing on the "Save" button.
                    </li>
                    <li>
                        Fill the IP addresses in the "Server IP Whitelist" with the list of addresses displayed below.
                    </li>
                </ol>
            </p>
        </div>

        <h4>Callback URL</h4>

        <code>https://{{ channel.callback_domain }}{% url 'courier.ln' channel.uuid %}</code>

        <hr/>

        <h4>IP Addresses</h4>

        {% for ip_address in ip_addresses %}
        <code>{{ip_address}}</code>
        {% endfor %}

        <hr/>
        """
    )

    claim_view = ClaimView

    schemes = [LINE_SCHEME]
    max_length = 1600
    attachment_support = False
    free_sending = True

    def send(self, channel, msg, text):
        channel_access_token = channel.config.get(Channel.CONFIG_AUTH_TOKEN)

        data = json.dumps({'to': msg.urn_path, 'messages': [{'type': 'text', 'text': text}]})

        start = time.time()
        headers = http_headers(extra={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % channel_access_token
        })
        send_url = 'https://api.line.me/v2/bot/message/push'

        event = HttpEvent('POST', send_url, data)

        try:
            response = requests.post(send_url, data=data, headers=headers)
            response.json()

            event.status_code = response.status_code
            event.response_body = response.text
        except Exception as e:
            raise SendException(six.text_type(e), event=event, start=start)

        if response.status_code not in [200, 201, 202]:  # pragma: needs cover
            raise SendException("Got non-200 response [%d] from Line" % response.status_code,
                                event=event, start=start)

        Channel.success(channel, msg, WIRED, start, event=event)
