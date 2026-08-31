from django.urls import reverse

from temba.channels.models import Channel
from temba.tests import TembaTest
from temba.utils import json


class AndroidTest(TembaTest):
    def test_register_unsupported_android(self):
        # remove our explicit country so it needs to be derived from channels
        self.org.root_location = None
        self.org.save(update_fields=("root_location",))

        Channel.objects.all().delete()

        reg_data = dict(cmds=[dict(cmd="gcm", gcm_id="GCM111", uuid="uuid"), dict(cmd="status", cc="RW", dev="Nexus")])

        # try a post register
        response = self.client.post(reverse("register"), json.dumps(reg_data), content_type="application/json")
        self.assertEqual(200, response.status_code)

        response_json = response.json()
        self.assertEqual(
            response_json,
            dict(cmds=[dict(cmd="reg", relayer_claim_code="*********", relayer_secret="0" * 64, relayer_id=-1)]),
        )

        # missing uuid raises
        reg_data = dict(cmds=[dict(cmd="fcm", fcm_id="FCM111"), dict(cmd="status", cc="RW", dev="Nexus")])

        with self.assertRaises(ValueError):
            self.client.post(reverse("register"), json.dumps(reg_data), content_type="application/json")

        # missing fcm_id raises
        reg_data = dict(cmds=[dict(cmd="fcm", uuid="uuid"), dict(cmd="status", cc="RW", dev="Nexus")])
        with self.assertRaises(ValueError):
            self.client.post(reverse("register"), json.dumps(reg_data), content_type="application/json")
