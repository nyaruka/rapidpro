import requests

from django.conf import settings
from django.urls import re_path
from django.utils.translation import gettext_lazy as _

from temba.contacts.models import URN
from temba.triggers.models import Trigger

from ...models import Channel, ChannelType
from .views import CheckCredentials, ClaimView


class FacebookAppType(ChannelType):
    """
    A Facebook channel
    """

    code = "FBA"
    name = "Facebook"
    category = ChannelType.Category.SOCIAL_MEDIA

    unique_addresses = True
    matching_addresses_updates = True

    courier_url = r"^fba/receive"
    schemes = [URN.FACEBOOK_SCHEME]

    claim_blurb = _(
        "Add a %(link)s bot to send and receive messages on behalf of one of your Facebook pages for free. You will "
        "need to connect your page by logging into your Facebook and checking the Facebook page to connect. "
        "On the Facebook page, navigate Settings > Page roles and verify you have an admin page role on the page."
    ) % {"link": '<a target="_blank" href="http://facebook.com">Facebook</a>'}
    claim_view = ClaimView

    menu_items = [dict(label=_("Check Credentials"), view_name="channels.types.facebookapp.check_credentials")]

    def get_urls(self):
        return [
            self.get_claim_url(),
            re_path(
                r"^(?P<uuid>[a-z0-9\-]+)/check_credentials/$",
                CheckCredentials.as_view(channel_type=self),
                name="check_credentials",
            ),
        ]

    def deactivate(self, channel):
        config = channel.config
        requests.delete(
            f"https://graph.facebook.com/v18.0/{channel.address}/subscribed_apps",
            params={"access_token": config[Channel.CONFIG_AUTH_TOKEN]},
        )

    def activate_trigger(self, trigger):
        # if this is new conversation trigger, register for the FB callback
        if trigger.trigger_type == Trigger.TYPE_NEW_CONVERSATION:
            # register for get_started events
            url = "https://graph.facebook.com/v18.0/me/messenger_profile"
            body = {"get_started": {"payload": "get_started"}}
            access_token = trigger.channel.config[Channel.CONFIG_AUTH_TOKEN]

            response = requests.post(
                url, json=body, params={"access_token": access_token}, headers={"Content-Type": "application/json"}
            )

            if response.status_code != 200:  # pragma: no cover
                raise Exception("Unable to update call to action: %s" % response.text)

    def deactivate_trigger(self, trigger):
        # for any new conversation triggers, clear out the call to action payload
        if trigger.trigger_type == Trigger.TYPE_NEW_CONVERSATION:
            # register for get_started events
            url = "https://graph.facebook.com/v18.0/me/messenger_profile"
            body = {"fields": ["get_started"]}
            access_token = trigger.channel.config[Channel.CONFIG_AUTH_TOKEN]

            response = requests.delete(
                url, json=body, params={"access_token": access_token}, headers={"Content-Type": "application/json"}
            )

            if response.status_code != 200:
                raise Exception("Unable to update call to action: %s" % response.text)

    def get_redact_values(self, channel) -> tuple:  # pragma: needs cover
        """
        Gets the values to redact from logs
        """
        return (settings.FACEBOOK_APPLICATION_SECRET, settings.FACEBOOK_WEBHOOK_SECRET)

    def get_error_ref_url(self, channel, code: str) -> str:
        return "https://developers.facebook.com/docs/messenger-platform/error-codes"

    def check_credentials(self, config: dict) -> bool:
        app_id = settings.FACEBOOK_APPLICATION_ID
        app_secret = settings.FACEBOOK_APPLICATION_SECRET
        url = "https://graph.facebook.com/v18.0/debug_token"

        if Channel.CONFIG_AUTH_TOKEN not in config:
            return False

        params = {
            "access_token": f"{app_id}|{app_secret}",
            "input_token": config[Channel.CONFIG_AUTH_TOKEN],
        }
        resp = requests.get(url, params=params)

        if resp.status_code == 200:
            return resp.json().get("data", dict()).get("is_valid", False)
        return False
