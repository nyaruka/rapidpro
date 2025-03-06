import xml.etree.ElementTree as ET

import requests

from django.forms import ValidationError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from temba.contacts.models import URN

from ...models import Channel, ChannelType
from .views import ClaimView


class BandwidthType(ChannelType):
    """
    An Bandwidth channel type (https://www.bandwidth.com/)
    """

    code = "BW"
    name = "Bandwidth"
    category = ChannelType.Category.PHONE
    beta_only = True

    courier_url = r"^bw/(?P<uuid>[a-z0-9\-]+)/(?P<action>receive|status)$"
    schemes = [URN.TEL_SCHEME]
    async_activation = False

    claim_view = ClaimView
    claim_blurb = _("If you have an %(link)s number, you can quickly connect it using their APIs.") % {
        "link": '<a target="_blank" href="https://www.bandwidth.com/">Bandwidth</a>'
    }

    def activate(self, channel):
        domain = channel.org.get_brand_domain()
        account_id = channel.config.get("account_id")

        if channel.role == "SR":
            receive_url = "https://" + domain + reverse("courier.bw", args=[channel.uuid, "receive"])
            status_url = "https://" + domain + reverse("courier.bw", args=[channel.uuid, "status"])

            application_xml = f"<Application><ServiceType>Messaging-V2</ServiceType><AppName>{domain}/{channel.uuid}</AppName><InboundCallbackUrl>{receive_url}</InboundCallbackUrl><OutboundCallbackUrl>{status_url}</OutboundCallbackUrl><RequestedCallbackTypes><CallbackType>message-delivered</CallbackType><CallbackType>message-failed</CallbackType><CallbackType>message-sending</CallbackType></RequestedCallbackTypes></Application>"
        elif channel.role == "CA":
            incoming_call_url = "https://" + domain + f"/mr/ivr/c/{channel.uuid}/incoming"
            status_call_url = "https://" + domain + f"/mr/ivr/c/{channel.uuid}/status"

            application_xml = f"<Application><ServiceType>Voice-V2</ServiceType><AppName>{domain}/{channel.uuid}</AppName><CallInitiatedCallbackUrl>{incoming_call_url}</CallInitiatedCallbackUrl><CallStatusCallbackUrl>{status_call_url}</CallStatusCallbackUrl></Application>"

        url = f"https://dashboard.bandwidth.com/api/accounts/{account_id}/applications"

        resp = requests.post(
            url,
            data=application_xml,
            auth=(channel.config.get(Channel.CONFIG_USERNAME), channel.config.get(Channel.CONFIG_PASSWORD)),
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )

        if resp.status_code not in [200, 201, 202]:  # pragma: no cover
            raise ValidationError(_("Unable to create bandwidth application"))

        resp_root = ET.fromstring(resp.content)
        application_id_elt = resp_root.find("Application").find("ApplicationId")

        channel.config["application_id"] = application_id_elt.text

        channel.save(update_fields=("config",))

    def deactivate(self, channel):
        account_id = channel.config.get("account_id")
        application_id = channel.config.get("application_id")

        url = f"https://dashboard.bandwidth.com/api/accounts/{account_id}/applications/{application_id}"

        resp = requests.delete(url)

        if resp.status_code != 200:  # pragma: no cover
            raise ValidationError(_("Error removing the bandwidth application"))
