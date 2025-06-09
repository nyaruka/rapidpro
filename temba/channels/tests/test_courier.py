from django.urls import reverse

from temba.tests import TembaTest


class CourierTest(TembaTest):
    def test_courier_urls(self):
        response = self.client.get(reverse("courier.t", args=[self.channel.uuid, "receive"]))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content, b"this URL should be mapped to a Courier instance")
