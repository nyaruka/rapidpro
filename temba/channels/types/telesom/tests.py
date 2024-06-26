from unittest.mock import patch

from django.urls import reverse

from temba.tests import TembaTest

from ...models import Channel


class TelesomTypeTest(TembaTest):
    @patch("socket.gethostbyname", return_value="123.123.123.123")
    def test_claim(self, mock_socket_hostname):
        Channel.objects.all().delete()

        self.login(self.admin)

        url = reverse("channels.types.telesom.claim")

        response = self.client.get(reverse("channels.channel_claim"))
        self.assertNotContains(response, url)

        self.org.timezone = "Africa/Mogadishu"
        self.org.save()

        # check that claim page URL appears on claim list page
        response = self.client.get(reverse("channels.channel_claim"))
        self.assertContains(response, url)

        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertEqual(response.context["view"].get_country({}), "Somalia")

        # try to claim a channel
        response = self.client.get(url)
        post_data = response.context["form"].initial

        post_data["country"] = "SO"
        post_data["url"] = "http://example.com/send.php"
        post_data["username"] = "uname"
        post_data["password"] = "pword"
        post_data["secret"] = "secret"
        post_data["number"] = "1212"

        response = self.client.post(url, post_data)
        channel = Channel.objects.get()

        self.assertEqual("SO", channel.country)
        self.assertTrue(channel.uuid)
        self.assertEqual(post_data["number"], channel.address)
        self.assertEqual(post_data["url"], channel.config["send_url"])
        self.assertEqual(post_data["username"], channel.config["username"])
        self.assertEqual(post_data["password"], channel.config["password"])
        self.assertEqual(post_data["secret"], channel.config["secret"])
        self.assertEqual("TS", channel.channel_type)

        config_url = reverse("channels.channel_configuration", args=[channel.uuid])
        self.assertRedirect(response, config_url)

        response = self.client.get(config_url)
        self.assertEqual(200, response.status_code)

        self.assertContains(response, reverse("courier.ts", args=[channel.uuid, "receive"]))
