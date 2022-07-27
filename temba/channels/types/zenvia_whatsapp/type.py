import requests

from django.forms import ValidationError
from django.urls import re_path, reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from temba.contacts.models import URN
from temba.request_logs.models import HTTPLog
from temba.utils.whatsapp.views import TemplatesView

from ...models import Channel, ChannelType
from .views import ClaimView

ZENVIA_MESSAGE_SUBSCRIPTION_ID = "zenvia_message_subscription_id"
ZENVIA_STATUS_SUBSCRIPTION_ID = "zenvia_status_subscription_id"


class ZenviaWhatsAppType(ChannelType):
    """
    An Zenvia WhatsApp channel
    """

    extra_links = [dict(name=_("Message Templates"), link="channels.types.zenvia_whatsapp.templates")]

    code = "ZVW"
    category = ChannelType.Category.SOCIAL_MEDIA

    courier_url = r"^zvw/(?P<uuid>[a-z0-9\-]+)/(?P<action>receive|status)$"

    name = "Zenvia WhatsApp"
    icon = "icon-whatsapp"

    claim_blurb = _(
        "If you have a %(link)s number, you can connect it to communicate with your WhatsApp contacts."
    ) % {"link": '<a href="https://www.zenvia.com/">Zenvia WhatsApp</a>'}

    claim_view = ClaimView

    schemes = [URN.WHATSAPP_SCHEME]
    max_length = 1600

    def get_urls(self):
        return [
            self.get_claim_url(),
            re_path(r"^(?P<uuid>[a-z0-9\-]+)/templates$", TemplatesView.as_view(), name="templates"),
        ]

    def update_webhook(self, channel, url, event_type):
        headers = {
            "X-API-TOKEN": channel.config[Channel.CONFIG_API_KEY],
            "Content-Type": "application/json",
        }

        conf_url = "https://api.zenvia.com/v2/subscriptions"

        # set our webhook
        payload = {
            "eventType": event_type,
            "webhook": {"url": url, "headers": {}},
            "status": "ACTIVE",
            "version": "v2",
            "criteria": {"channel": "whatsapp"},
        }
        if event_type == "MESSAGE":
            payload["criteria"]["direction"] = "IN"

        resp = requests.post(conf_url, json=payload, headers=headers)

        if resp.status_code != 200:
            raise ValidationError(
                _("Unable to register webhook subscriptions: %(resp)s"), params={"resp": resp.content}
            )

        return resp.json()["id"]

    def deactivate(self, channel):
        headers = {
            "X-API-TOKEN": channel.config[Channel.CONFIG_API_KEY],
            "Content-Type": "application/json",
        }

        subscription_ids = [
            channel.config.get(ZENVIA_MESSAGE_SUBSCRIPTION_ID),
            channel.config.get(ZENVIA_STATUS_SUBSCRIPTION_ID),
        ]

        errored = False

        for subscription_id in subscription_ids:
            if not subscription_id:  # pragma: needs cover
                continue

            conf_url = f"https://api.zenvia.com/v2/subscriptions/{subscription_id}"
            resp = requests.delete(conf_url, headers=headers)

            if resp.status_code != 204:
                errored = True

        if errored:
            raise ValidationError(_("Unable to remove webhook subscriptions: %(resp)s"), params={"resp": resp.content})

    def activate(self, channel):
        domain = channel.org.get_brand_domain()

        receive_url = "https://" + domain + reverse("courier.zvw", args=[channel.uuid, "receive"])
        messageSubscriptionId = self.update_webhook(channel, receive_url, "MESSAGE")

        channel.config[ZENVIA_MESSAGE_SUBSCRIPTION_ID] = messageSubscriptionId

        status_url = "https://" + domain + reverse("courier.zvw", args=[channel.uuid, "status"])
        statusSubscriptionId = self.update_webhook(channel, status_url, "MESSAGE_STATUS")

        channel.config[ZENVIA_STATUS_SUBSCRIPTION_ID] = statusSubscriptionId

        channel.save()

    def get_api_templates(self, channel):
        if Channel.CONFIG_API_KEY not in channel.config:  # pragma: no cover
            return [], False

        start = timezone.now()
        try:
            template_data = []

            url = "https://api.zenvia.com/v2/templates"
            headers = {
                "X-API-TOKEN": channel.config[Channel.CONFIG_API_KEY],
                "Content-Type": "application/json",
            }
            resp = requests.get(url, headers=headers)
            elapsed = (timezone.now() - start).total_seconds() * 1000
            HTTPLog.create_from_response(
                HTTPLog.WHATSAPP_TEMPLATES_SYNCED, url, resp, channel=channel, request_time=elapsed
            )
            if resp.status_code != 200:  # pragma: no cover
                return [], False

            # remap the response as the WA API template data
            response_json = resp.json()
            for elt in response_json:
                if elt["channel"] != "WHATSAPP":
                    continue

                components = []
                for elt_component_key in ["header", "body", "footer"]:
                    if elt_component_key in elt["components"]:
                        components.append(
                            dict(type=elt_component_key.upper(), text=elt["components"][elt_component_key]["text"])
                        )

                template_data.append(
                    dict(
                        name=elt["name"],
                        id=elt["id"],
                        language=elt["locale"],
                        status=elt["status"],
                        category=elt["category"],
                        components=components,
                    )
                )

            return template_data, True
        except requests.RequestException as e:
            HTTPLog.create_from_exception(HTTPLog.WHATSAPP_TEMPLATES_SYNCED, url, e, start, channel=channel)
            return [], False
