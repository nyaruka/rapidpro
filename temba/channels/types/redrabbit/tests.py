from django.urls import reverse

from temba.tests import TembaTest

from ...models import Channel


class RedRabbitTypeTest(TembaTest):
    def test_claim(self):
        Channel.objects.all().delete()

        url = reverse("channels.types.redrabbit.claim")

        self.login(self.admin)

        # check that claim page URL appears on claim list page
        response = self.client.get(reverse("channels.channel_claim"))
        self.assertNotContains(response, url)

        # try to claim a channel
        response = self.client.get(url)
        post_data = response.context["form"].initial

        post_data["country"] = "JO"
        post_data["number"] = "250788123123"
        post_data["username"] = "user1"
        post_data["password"] = "pass1"

        response = self.client.post(url, post_data)

        channel = Channel.objects.get()

        self.assertEqual("JO", channel.country)
        self.assertEqual(post_data["username"], channel.config["username"])
        self.assertEqual(post_data["password"], channel.config["password"])
        self.assertEqual("+250788123123", channel.address)
        self.assertEqual("RR", channel.channel_type)

        read_url = reverse("channels.channel_read", args=[channel.uuid])
        self.assertRedirect(response, read_url)

        Channel.objects.all().delete()

        response = self.client.get(url)
        post_data = response.context["form"].initial

        post_data["country"] = "JO"
        post_data["number"] = "20050"
        post_data["username"] = "user1"
        post_data["password"] = "pass1"

        response = self.client.post(url, post_data)

        channel = Channel.objects.get()

        self.assertEqual("JO", channel.country)
        self.assertEqual(post_data["username"], channel.config["username"])
        self.assertEqual(post_data["password"], channel.config["password"])
        self.assertEqual("20050", channel.address)
        self.assertEqual("RR", channel.channel_type)
