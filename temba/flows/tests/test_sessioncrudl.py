import io

from django.urls import reverse
from django.utils import timezone

from temba.flows.models import FlowSession
from temba.tests import TembaTest
from temba.utils import json, s3


class FlowSessionCRUDLTest(TembaTest):
    def test_session_json(self):
        contact = self.create_contact("Bob", phone="+1234567890")
        output = {"uuid": "49165a56-de7c-4048-9103-6aa81be6ea94", "status": "waiting"}
        session = FlowSession.objects.create(
            uuid=output["uuid"],
            contact=contact,
            status=FlowSession.STATUS_WAITING,
            output=output,
            created_on=timezone.now(),
        )

        # normal users can't see session json
        json_url = reverse("flows.flowsession_json", args=[session.uuid])
        response = self.client.get(json_url)
        self.assertLoginRedirect(response)

        self.login(self.admin)
        response = self.client.get(json_url)
        self.assertLoginRedirect(response)

        # but logged in as a CS rep we can
        self.login(self.customer_support, choose_org=self.org)

        response = self.client.get(json_url)
        self.assertEqual(200, response.status_code)

        response_json = json.loads(response.content)
        self.assertEqual("Nyaruka", response_json["_metadata"]["org"])
        self.assertEqual("49165a56-de7c-4048-9103-6aa81be6ea94", response_json["uuid"])

        # now try with an s3 session
        s3.client().put_object(
            Bucket="test-sessions", Key="c/session.json", Body=io.BytesIO(json.dumps(output).encode())
        )
        FlowSession.objects.filter(id=session.id).update(
            output_url="http://minio:9000/test-sessions/c/session.json", output=None
        )

        # fetch our contact history
        response = self.client.get(json_url)
        self.assertEqual(200, response.status_code)
        self.assertEqual("Nyaruka", response_json["_metadata"]["org"])
        self.assertEqual("49165a56-de7c-4048-9103-6aa81be6ea94", response_json["uuid"])
