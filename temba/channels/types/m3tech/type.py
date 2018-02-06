from __future__ import unicode_literals, absolute_import

import json
import time
import requests
import six

from django.utils.http import urlencode
from django.utils.translation import ugettext_lazy as _

from temba.channels.views import AuthenticatedExternalClaimView
from temba.contacts.models import TEL_SCHEME
from temba.msgs.models import WIRED
from temba.utils.http import HttpEvent, http_headers
from ...models import Channel, ChannelType, SendException, Encoding


class M3TechType(ChannelType):
    """
    An M3 Tech channel (http://m3techservice.com)
    """

    code = 'M3'
    category = ChannelType.Category.PHONE

    name = "M3 Tech"

    claim_blurb = _("""Easily add a two way number you have configured with <a href="http://m3techservice.com">M3 Tech</a> using their APIs.""")

    configuration_blurb = _(
        """
        <h4>
        To finish configuring your connection you'll need to notify M3Tech of the following callback URLs:
        </h4>

        <h4>Received URL</h4>

        <code>https://{{ channel.callback_domain }}{% url 'courier.m3' channel.uuid 'receive' %}</code>

        <p>
        When a new message is received by M3Tech, it should notify us with a POST to the following URL, passing
        the following parameters: 'from' and 'text'
        </p>

        <pre class="prettyprint example" >
        POST https://{{ channel.callback_domain }}{% url 'courier.m3' channel.uuid 'receive' %}
            from=%2B250788123123&text=Love+is+patient.+Love+is+kind.
        </pre>
        <hr/>

        <h4>Sent URL</h4>

        <code>https://{{ channel.callback_domain }}{% url 'courier.m3' channel.uuid 'sent' %}</code>

        <p>
        When M3Tech successfully sends a message, it should notify us with a POST to the following URL, passing
        the id of the message as the parameter 'id' (reporting sent messages is optional)
        </p>

        <pre class="prettyprint example" >
        POST https://{{ channel.callback_domain }}{% url 'courier.m3' channel.uuid 'sent' %}
            id=2599235
        </pre>
        <hr/>

        <h4>Delivered URL</h4>

        <code>https://{{ channel.callback_domain }}{% url 'courier.m3' channel.uuid 'delivered' %}</code>

        <p>
        When M3Tech successfully delivers a message, it should notify us with a POST to the following URL, passing
        the id of the message as the parameter 'id' (reporting deliveries is optional)
        </p>

        <pre class="prettyprint example" >
        POST https://{{ channel.callback_domain }}{% url 'courier.m3' channel.uuid 'delivered' %}
            id=2599235
        </pre>
        <hr/>

        <h4>Failed URL</h4>

        <code>https://{{ channel.callback_domain }}{% url 'courier.m3' channel.uuid 'failed' %}</code>

        <p>
        If M3Tech fails to send an outgoing message, it should notify us with a POST to the following URL, passing
        the id of the message as the parameter 'id' (reporting failed sends is optional)
        </p>

        <pre class="prettyprint example" >
        POST https://{{ channel.callback_domain }}{% url 'courier.m3' channel.uuid 'failed' %}
            id=2599235
        </pre>

        <hr/>
        """
    )

    claim_view = AuthenticatedExternalClaimView

    schemes = [TEL_SCHEME]
    max_length = 160
    attachment_support = False

    def is_available_to(self, user):
        org = user.get_org()
        return org.timezone and six.text_type(org.timezone) in ["Asia/Karachi"]

    def send(self, channel, msg, text):

        # determine our encoding
        encoding, text = Channel.determine_encoding(text, replace=True)

        # if this looks like unicode, ask m3tech to send as unicode
        if encoding == Encoding.UNICODE:
            sms_type = '7'
        else:
            sms_type = '0'

        url = 'https://secure.m3techservice.com/GenericServiceRestAPI/api/SendSMS'
        payload = {'AuthKey': 'm3-Tech',
                   'UserId': channel.config[Channel.CONFIG_USERNAME],
                   'Password': channel.config[Channel.CONFIG_PASSWORD],
                   'MobileNo': msg.urn_path.lstrip('+'),
                   'MsgId': msg.id,
                   'SMS': text,
                   'MsgHeader': channel.address.lstrip('+'),
                   'SMSType': sms_type,
                   'HandsetPort': '0',
                   'SMSChannel': '0',
                   'Telco': '0'}

        event = HttpEvent('GET', url + "?" + urlencode(payload))

        start = time.time()

        try:
            response = requests.get(url, params=payload, headers=http_headers(), timeout=5)
            event.status_code = response.status_code
            event.response_body = response.text

        except Exception as e:
            raise SendException(six.text_type(e), event=event, start=start)

        if response.status_code != 200 and response.status_code != 201 and response.status_code != 202:
            raise SendException("Got non-200 response [%d] from API" % response.status_code,
                                event=event, start=start)

        # our response is JSON and should contain a 0 as a status code:
        # [{"Response":"0"}]
        try:
            response_code = json.loads(response.text)[0]["Response"]
        except Exception as e:
            response_code = str(e)

        # <Response>0</Response>
        if response_code != "0":
            raise SendException("Received non-zero status from API: %s" % str(response_code),
                                event=event, start=start)

        Channel.success(channel, msg, WIRED, start, event=event)
