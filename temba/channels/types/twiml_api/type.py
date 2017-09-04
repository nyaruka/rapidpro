from __future__ import unicode_literals, absolute_import

import time

import six

from django.utils.translation import ugettext_lazy as _
from twilio import TwilioRestException

from temba.channels.types.twiml_api.views import ClaimView
from temba.contacts.models import TEL_SCHEME
from temba.msgs.models import WIRED, Attachment
from temba.orgs.models import ACCOUNT_SID, ACCOUNT_TOKEN
from temba.utils.twilio import TembaTwilioRestClient
from ...models import Channel, ChannelType, SendException


class TwimlAPIType(ChannelType):
    """
    An Twiml API channel
    """

    code = 'TW'
    category = ChannelType.Category.PHONE

    name = "TwiML Rest API"
    slug = "twiml_api"
    icon = "icon-channel-twilio",

    claim_blurb = _("""Connect to a service that speaks TwiML. You can use this to connect to TwiML compatible services outside of Twilio.""")
    claim_view = ClaimView

    schemes = [TEL_SCHEME]
    max_length = 1600

    attachment_support = True

    def send(self, channel, msg, text):
        callback_url = Channel.build_twilio_callback_url(channel.uuid, msg.id)

        start = time.time()
        media_urls = []

        if msg.attachments:
            # for now we only support sending one attachment per message but this could change in future
            attachment = Attachment.parse_all(msg.attachments)[0]
            media_urls = [attachment.url]

        if channel.channel_type == 'TW':  # pragma: no cover
            config = channel.config
            client = TembaTwilioRestClient(config.get(ACCOUNT_SID), config.get(ACCOUNT_TOKEN),
                                           base=config.get(Channel.CONFIG_SEND_URL))
        else:
            client = TembaTwilioRestClient(channel.org_config[ACCOUNT_SID], channel.org_config[ACCOUNT_TOKEN])

        try:
            if channel.channel_type == Channel.TYPE_TWILIO_MESSAGING_SERVICE:
                messaging_service_sid = channel.config['messaging_service_sid']
                client.messages.create(to=msg.urn_path,
                                       messaging_service_sid=messaging_service_sid,
                                       body=text,
                                       media_url=media_urls,
                                       status_callback=callback_url)
            else:
                client.messages.create(to=msg.urn_path,
                                       from_=channel.address,
                                       body=text,
                                       media_url=media_urls,
                                       status_callback=callback_url)

            Channel.success(channel, msg, WIRED, start, events=client.messages.events)

        except TwilioRestException as e:
            fatal = False

            # user has blacklisted us, stop the contact
            if e.code == 21610:
                from temba.contacts.models import Contact
                fatal = True
                contact = Contact.objects.get(id=msg.contact)
                contact.stop(contact.modified_by)

            raise SendException(e.msg, events=client.messages.events, fatal=fatal)

        except Exception as e:
            raise SendException(six.text_type(e), events=client.messages.events)
