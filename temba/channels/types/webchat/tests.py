from django.urls import reverse

from temba.channels.models import Channel
from temba.tests import TembaTest


class WebChatTypeTest(TembaTest):
    def test_claim(self):
        claim_url = reverse("channels.types.webchat.claim")

        # not available to regular users
        self.login(self.admin)

        response = self.client.get(reverse("channels.channel_claim_all"))
        self.assertNotContains(response, claim_url)

        # and can't be claimed by them directly either
        response = self.client.post(claim_url, {})
        self.assertEqual(404, response.status_code)

        # but is available to staff
        self.login(self.customer_support, choose_org=self.org)

        response = self.client.get(reverse("channels.channel_claim_all"))
        self.assertContains(response, claim_url)

        response = self.client.post(claim_url, {})
        self.assertEqual(302, response.status_code)

        channel = Channel.objects.get(channel_type="WCH")
        self.assertEqual("WebChat", channel.name)
        self.assertIsNone(channel.address)
        self.assertEqual(["webchat"], channel.schemes)
        self.assertEqual({}, channel.config)
        self.assertEqual(reverse("channels.channel_configuration", args=[channel.uuid]), response.url)

        # config page shows the channel UUID that the embedded widget connects with
        response = self.client.get(reverse("channels.channel_configuration", args=[channel.uuid]))
        self.assertContains(response, str(channel.uuid))
