from django.urls import reverse

from temba.channels.models import Channel
from temba.tests import TembaTest


class ChipTest(TembaTest):
    def test_channel(self):
        claim_url = reverse("channels.types.chip.claim")

        self.login(self.admin)

        response = self.client.get(reverse("channels.channel_claim_all"))
        self.assertNotContains(response, claim_url)

        self.login(self.customer_support, choose_org=self.org)

        response = self.client.get(reverse("channels.channel_claim_all"))
        self.assertContains(response, claim_url)

        response = self.client.post(claim_url)
        self.assertEqual(response.status_code, 302)

        self.assertEqual(1, Channel.objects.filter(channel_type="CHP").count())
