from django.urls import reverse

from temba.tests import FlowFileTest


class IVRTests(FlowFileTest):
    def test_mailroom_ivr_view(self):
        response = self.client.get(reverse("mailroom.ivr_handler", args=[self.channel.uuid, "incoming"]))
        self.assertEqual(500, response.status_code)
