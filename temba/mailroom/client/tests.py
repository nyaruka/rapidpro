from datetime import datetime, timezone as tzone
from decimal import Decimal
from unittest.mock import patch

from django.test import override_settings

from temba.mailroom.client import ContactSpec, RequestException, get_client
from temba.schedules.models import Schedule
from temba.tests import MockJsonResponse, MockResponse, TembaTest
from temba.utils import json

from .client import BroadcastPreview, Exclusions, Inclusions, StartPreview, URNResult, modifiers, ScheduleSpec
from .exceptions import (
    EmptyBroadcastException,
    FlowValidationException,
    QueryValidationException,
    URNValidationException,
)


class MailroomClientTest(TembaTest):
    def test_version(self):
        with patch("requests.get") as mock_get:
            mock_get.return_value = MockJsonResponse(200, {"version": "5.3.4"})
            version = get_client().version()

        self.assertEqual("5.3.4", version)

    @patch("requests.post")
    def test_android_event(self, mock_post):
        mock_post.return_value = MockJsonResponse(200, {"id": 12345})
        response = get_client().android_event(
            org_id=self.org.id,
            channel_id=12,
            phone="+1234567890",
            event_type="mo_miss",
            extra={"duration": 45},
            occurred_on=datetime(2024, 4, 1, 16, 28, 30, 0, tzone.utc),
        )

        self.assertEqual({"id": 12345}, response)

        mock_post.assert_called_once_with(
            "http://localhost:8090/mr/android/event",
            headers={"User-Agent": "Temba"},
            json={
                "org_id": self.org.id,
                "channel_id": 12,
                "phone": "+1234567890",
                "event_type": "mo_miss",
                "extra": {"duration": 45},
                "occurred_on": "2024-04-01T16:28:30+00:00",
            },
        )

    @patch("requests.post")
    def test_android_message(self, mock_post):
        mock_post.return_value = MockJsonResponse(200, {"id": 12345})
        response = get_client().android_message(
            org_id=self.org.id,
            channel_id=12,
            phone="+1234567890",
            text="hello",
            received_on=datetime(2024, 4, 1, 16, 28, 30, 0, tzone.utc),
        )

        self.assertEqual({"id": 12345}, response)

        mock_post.assert_called_once_with(
            "http://localhost:8090/mr/android/message",
            headers={"User-Agent": "Temba"},
            json={
                "org_id": self.org.id,
                "channel_id": 12,
                "phone": "+1234567890",
                "text": "hello",
                "received_on": "2024-04-01T16:28:30+00:00",
            },
        )

    @patch("requests.post")
    def test_contact_create(self, mock_post):
        mock_post.return_value = MockJsonResponse(200, {"contact": {"id": 1234, "name": "", "language": ""}})

        # try with empty contact spec
        response = get_client().contact_create(
            self.org.id, self.admin.id, ContactSpec(name="", language="", urns=[], fields={}, groups=[])
        )

        self.assertEqual({"id": 1234, "name": "", "language": ""}, response["contact"])
        mock_post.assert_called_once_with(
            "http://localhost:8090/mr/contact/create",
            headers={"User-Agent": "Temba"},
            json={
                "org_id": self.org.id,
                "user_id": self.admin.id,
                "contact": {"name": "", "language": "", "urns": [], "fields": {}, "groups": []},
            },
        )

        mock_post.reset_mock()
        mock_post.return_value = MockJsonResponse(200, {"contact": {"id": 1234, "name": "Bob", "language": "eng"}})

        response = get_client().contact_create(
            self.org.id,
            self.admin.id,
            ContactSpec(
                name="Bob",
                language="eng",
                urns=["tel:+123456789"],
                fields={"age": "39", "gender": "M"},
                groups=["d5b1770f-0fb6-423b-86a0-b4d51096b99a"],
            ),
        )

        self.assertEqual({"id": 1234, "name": "Bob", "language": "eng"}, response["contact"])
        mock_post.assert_called_once_with(
            "http://localhost:8090/mr/contact/create",
            headers={"User-Agent": "Temba"},
            json={
                "org_id": self.org.id,
                "user_id": self.admin.id,
                "contact": {
                    "name": "Bob",
                    "language": "eng",
                    "urns": ["tel:+123456789"],
                    "fields": {"age": "39", "gender": "M"},
                    "groups": ["d5b1770f-0fb6-423b-86a0-b4d51096b99a"],
                },
            },
        )

    @patch("requests.post")
    def test_contact_export(self, mock_post):
        mock_post.return_value = MockJsonResponse(200, {"contact_ids": [123, 234]})

        response = get_client().contact_export(self.org.id, 234, "age = 42")

        self.assertEqual({"contact_ids": [123, 234]}, response)
        mock_post.assert_called_once_with(
            "http://localhost:8090/mr/contact/export",
            headers={"User-Agent": "Temba"},
            json={"org_id": self.org.id, "group_id": 234, "query": "age = 42"},
        )

    @patch("requests.post")
    def test_contact_export_preview(self, mock_post):
        mock_post.return_value = MockJsonResponse(200, {"total": 123})

        response = get_client().contact_export_preview(self.org.id, 234, "age = 42")

        self.assertEqual({"total": 123}, response)
        mock_post.assert_called_once_with(
            "http://localhost:8090/mr/contact/export_preview",
            headers={"User-Agent": "Temba"},
            json={"org_id": self.org.id, "group_id": 234, "query": "age = 42"},
        )

    @patch("requests.post")
    def test_contact_inspect(self, mock_post):
        mock_post.return_value = MockJsonResponse(200, {"101": {}, "102": {}})

        response = get_client().contact_inspect(self.org.id, [101, 102])

        self.assertEqual({"101": {}, "102": {}}, response)
        mock_post.assert_called_once_with(
            "http://localhost:8090/mr/contact/inspect",
            headers={"User-Agent": "Temba"},
            json={"org_id": self.org.id, "contact_ids": [101, 102]},
        )

    @patch("requests.post")
    def test_contact_interrupt(self, mock_post):
        mock_post.return_value = MockJsonResponse(200, {"sessions": 1})

        response = get_client().contact_interrupt(self.org.id, 3, 345)

        self.assertEqual({"sessions": 1}, response)
        mock_post.assert_called_once_with(
            "http://localhost:8090/mr/contact/interrupt",
            headers={"User-Agent": "Temba"},
            json={"org_id": self.org.id, "user_id": 3, "contact_id": 345},
        )

    def test_contact_modify(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value = MockJsonResponse(
                200,
                {
                    "1": {
                        "contact": {
                            "uuid": "6393abc0-283d-4c9b-a1b3-641a035c34bf",
                            "id": 1,
                            "name": "Frank",
                            "timezone": "America/Los_Angeles",
                            "created_on": "2018-07-06T12:30:00.123457Z",
                        },
                        "events": [
                            {
                                "type": "contact_groups_changed",
                                "created_on": "2018-07-06T12:30:03.123456789Z",
                                "groups_added": [{"uuid": "c153e265-f7c9-4539-9dbc-9b358714b638", "name": "Doctors"}],
                            }
                        ],
                    }
                },
            )

            response = get_client().contact_modify(
                1,
                1,
                [1],
                [
                    modifiers.Name(name="Bob"),
                    modifiers.Language(language="fra"),
                    modifiers.Field(field=modifiers.FieldRef(key="age", name="Age"), value="43"),
                    modifiers.Status(status="blocked"),
                    modifiers.Groups(
                        groups=[modifiers.GroupRef(uuid="c153e265-f7c9-4539-9dbc-9b358714b638", name="Doctors")],
                        modification="add",
                    ),
                    modifiers.URNs(urns=["+tel+1234567890"], modification="append"),
                ],
            )
            self.assertEqual("6393abc0-283d-4c9b-a1b3-641a035c34bf", response["1"]["contact"]["uuid"])
            mock_post.assert_called_once_with(
                "http://localhost:8090/mr/contact/modify",
                headers={"User-Agent": "Temba"},
                json={
                    "org_id": 1,
                    "user_id": 1,
                    "contact_ids": [1],
                    "modifiers": [
                        {"type": "name", "name": "Bob"},
                        {"type": "language", "language": "fra"},
                        {"type": "field", "field": {"key": "age", "name": "Age"}, "value": "43"},
                        {"type": "status", "status": "blocked"},
                        {
                            "type": "groups",
                            "groups": [{"uuid": "c153e265-f7c9-4539-9dbc-9b358714b638", "name": "Doctors"}],
                            "modification": "add",
                        },
                        {"type": "urns", "urns": ["+tel+1234567890"], "modification": "append"},
                    ],
                },
            )

    @patch("requests.post")
    def test_contact_search(self, mock_post):
        mock_post.return_value = MockJsonResponse(
            200,
            {
                "query": 'name ~ "frank"',
                "contact_ids": [1, 2],
                "total": 2,
                "offset": 0,
                "metadata": {"attributes": ["name"]},
            },
        )
        response = get_client().contact_search(1, 2, "frank", "-created_on")

        self.assertEqual('name ~ "frank"', response.query)
        self.assertEqual(["name"], response.metadata.attributes)
        mock_post.assert_called_once_with(
            "http://localhost:8090/mr/contact/search",
            headers={"User-Agent": "Temba"},
            json={
                "query": "frank",
                "org_id": 1,
                "group_id": 2,
                "exclude_ids": (),
                "offset": 0,
                "sort": "-created_on",
            },
        )

    @patch("requests.post")
    def test_contact_urns(self, mock_post):
        mock_post.return_value = MockJsonResponse(
            200, {"urns": [{"normalized": "tel:+1234", "contact_id": 345}, {"normalized": "webchat:3a2ef3"}]}
        )

        response = get_client().contact_urns(self.org.id, ["tel:+1234", "webchat:3a2ef3"])

        self.assertEqual(
            [URNResult(normalized="tel:+1234", contact_id=345), URNResult(normalized="webchat:3a2ef3")], response
        )
        mock_post.assert_called_once_with(
            "http://localhost:8090/mr/contact/urns",
            headers={"User-Agent": "Temba"},
            json={"org_id": self.org.id, "urns": ["tel:+1234", "webchat:3a2ef3"]},
        )

    def test_flow_change_language(self):
        flow_def = {"nodes": [{"val": Decimal("1.23")}]}

        with patch("requests.post") as mock_post:
            mock_post.return_value = MockJsonResponse(200, {"language": "spa"})
            migrated = get_client().flow_change_language(flow_def, language="spa")

            self.assertEqual({"language": "spa"}, migrated)

        call = mock_post.call_args

        self.assertEqual(("http://localhost:8090/mr/flow/change_language",), call[0])
        self.assertEqual({"User-Agent": "Temba", "Content-Type": "application/json"}, call[1]["headers"])
        self.assertEqual({"flow": flow_def, "language": "spa"}, json.loads(call[1]["data"]))

    @override_settings(TESTING=False)
    def test_flow_inspect(self):
        flow_def = {"nodes": [{"val": Decimal("1.23")}]}

        with patch("requests.post") as mock_post:
            mock_post.return_value = MockJsonResponse(200, {"dependencies": []})
            info = get_client().flow_inspect(self.org.id, flow_def)

            self.assertEqual({"dependencies": []}, info)

        call = mock_post.call_args

        self.assertEqual(("http://localhost:8090/mr/flow/inspect",), call[0])
        self.assertEqual({"User-Agent": "Temba", "Content-Type": "application/json"}, call[1]["headers"])
        self.assertEqual({"org_id": self.org.id, "flow": flow_def}, json.loads(call[1]["data"]))

    def test_flow_migrate(self):
        flow_def = {"nodes": [{"val": Decimal("1.23")}]}

        with patch("requests.post") as mock_post:
            mock_post.return_value = MockJsonResponse(200, {"name": "Migrated!"})
            migrated = get_client().flow_migrate(flow_def, to_version="13.1.0")

            self.assertEqual({"name": "Migrated!"}, migrated)

        call = mock_post.call_args

        self.assertEqual(("http://localhost:8090/mr/flow/migrate",), call[0])
        self.assertEqual({"User-Agent": "Temba", "Content-Type": "application/json"}, call[1]["headers"])
        self.assertEqual({"flow": flow_def, "to_version": "13.1.0"}, json.loads(call[1]["data"]))

    def test_flow_start_preview(self):
        with patch("requests.post") as mock_post:
            mock_resp = {"query": 'group = "Farmers" AND status = "active"', "total": 2345}
            mock_post.return_value = MockJsonResponse(200, mock_resp)
            preview = get_client().flow_start_preview(
                self.org.id,
                flow_id=12,
                include=Inclusions(
                    group_uuids=["1e42a9dd-3683-477d-a3d8-19db951bcae0"],
                    contact_uuids=["ad32f9a9-e26e-4628-b39b-a54f177abea8"],
                ),
                exclude=Exclusions(non_active=True, not_seen_since_days=30),
            )

            self.assertEqual(StartPreview(query='group = "Farmers" AND status = "active"', total=2345), preview)

        call = mock_post.call_args

        self.assertEqual(("http://localhost:8090/mr/flow/start_preview",), call[0])
        self.assertEqual({"User-Agent": "Temba", "Content-Type": "application/json"}, call[1]["headers"])
        self.assertEqual(
            {
                "org_id": self.org.id,
                "flow_id": 12,
                "include": {
                    "group_uuids": ["1e42a9dd-3683-477d-a3d8-19db951bcae0"],
                    "contact_uuids": ["ad32f9a9-e26e-4628-b39b-a54f177abea8"],
                    "query": "",
                },
                "exclude": {
                    "non_active": True,
                    "in_a_flow": False,
                    "started_previously": False,
                    "not_seen_since_days": 30,
                },
            },
            json.loads(call[1]["data"]),
        )

    def test_msg_broadcast(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value = MockJsonResponse(200, {"id": 123})
            resp = get_client().msg_broadcast(
                self.org.id,
                self.admin.id,
                {"eng": {"text": "Hello"}},
                "eng",
                [12, 23],
                [123, 234],
                ["tel:1234"],
                "age > 20",
                "",
                567,
                ScheduleSpec(start="2024-06-20T16:23:30Z", repeat_period=Schedule.REPEAT_DAILY),
            )

            self.assertEqual({"id": 123}, resp)

        call = mock_post.call_args

        self.assertEqual(("http://localhost:8090/mr/msg/broadcast",), call[0])
        self.assertEqual({"User-Agent": "Temba", "Content-Type": "application/json"}, call[1]["headers"])
        self.assertEqual(
            {
                "org_id": self.org.id,
                "user_id": self.admin.id,
                "translations": {"eng": {"text": "Hello"}},
                "base_language": "eng",
                "group_ids": [12, 23],
                "contact_ids": [123, 234],
                "urns": ["tel:1234"],
                "query": "age > 20",
                "node_uuid": "",
                "optin_id": 567,
                "schedule": {"start": "2024-06-20T16:23:30Z", "repeat_period": "D", "repeat_days_of_week": None},
            },
            json.loads(call[1]["data"]),
        )

    def test_msg_broadcast_preview(self):
        with patch("requests.post") as mock_post:
            mock_resp = {"query": 'group = "Farmers" AND status = "active"', "total": 2345}
            mock_post.return_value = MockJsonResponse(200, mock_resp)
            preview = get_client().msg_broadcast_preview(
                self.org.id,
                include=Inclusions(
                    group_uuids=["1e42a9dd-3683-477d-a3d8-19db951bcae0"],
                    contact_uuids=["ad32f9a9-e26e-4628-b39b-a54f177abea8"],
                ),
                exclude=Exclusions(non_active=True, not_seen_since_days=30),
            )

            self.assertEqual(BroadcastPreview(query='group = "Farmers" AND status = "active"', total=2345), preview)

        call = mock_post.call_args

        self.assertEqual(("http://localhost:8090/mr/msg/broadcast_preview",), call[0])
        self.assertEqual({"User-Agent": "Temba", "Content-Type": "application/json"}, call[1]["headers"])
        self.assertEqual(
            {
                "org_id": self.org.id,
                "include": {
                    "group_uuids": ["1e42a9dd-3683-477d-a3d8-19db951bcae0"],
                    "contact_uuids": ["ad32f9a9-e26e-4628-b39b-a54f177abea8"],
                    "query": "",
                },
                "exclude": {
                    "non_active": True,
                    "in_a_flow": False,
                    "started_previously": False,
                    "not_seen_since_days": 30,
                },
            },
            json.loads(call[1]["data"]),
        )

    @patch("requests.post")
    def test_msg_handle(self, mock_post):
        mock_post.return_value = MockJsonResponse(200, {"msg_ids": [12345]})
        response = get_client().msg_handle(org_id=self.org.id, msg_ids=[12345, 67890])

        self.assertEqual({"msg_ids": [12345]}, response)

        mock_post.assert_called_once_with(
            "http://localhost:8090/mr/msg/handle",
            headers={"User-Agent": "Temba"},
            json={"org_id": self.org.id, "msg_ids": [12345, 67890]},
        )

    @patch("requests.post")
    def test_msg_resend(self, mock_post):
        mock_post.return_value = MockJsonResponse(200, {"msg_ids": [12345]})
        response = get_client().msg_resend(org_id=self.org.id, msg_ids=[12345, 67890])

        self.assertEqual({"msg_ids": [12345]}, response)

        mock_post.assert_called_once_with(
            "http://localhost:8090/mr/msg/resend",
            headers={"User-Agent": "Temba"},
            json={"org_id": self.org.id, "msg_ids": [12345, 67890]},
        )

    @patch("requests.post")
    def test_msg_send(self, mock_post):
        mock_post.return_value = MockJsonResponse(200, {"id": 12345})
        response = get_client().msg_send(
            org_id=self.org.id, user_id=self.admin.id, contact_id=123, text="hi", attachments=[], ticket_id=345
        )

        self.assertEqual({"id": 12345}, response)

        mock_post.assert_called_once_with(
            "http://localhost:8090/mr/msg/send",
            headers={"User-Agent": "Temba"},
            json={
                "org_id": self.org.id,
                "user_id": self.admin.id,
                "contact_id": 123,
                "text": "hi",
                "attachments": [],
                "ticket_id": 345,
            },
        )

    def test_po_export(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value = MockResponse(200, 'msgid "Red"\nmsgstr "Rojo"\n\n')
            response = get_client().po_export(self.org.id, [123, 234], "spa")

            self.assertEqual(b'msgid "Red"\nmsgstr "Rojo"\n\n', response)

        mock_post.assert_called_once_with(
            "http://localhost:8090/mr/po/export",
            headers={"User-Agent": "Temba"},
            json={"org_id": self.org.id, "flow_ids": [123, 234], "language": "spa"},
        )

    def test_po_import(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value = MockJsonResponse(200, {"flows": []})
            response = get_client().po_import(self.org.id, [123, 234], "spa", b'msgid "Red"\nmsgstr "Rojo"\n\n')

            self.assertEqual({"flows": []}, response)

        mock_post.assert_called_once_with(
            "http://localhost:8090/mr/po/import",
            headers={"User-Agent": "Temba"},
            data={"org_id": self.org.id, "flow_ids": [123, 234], "language": "spa"},
            files={"po": b'msgid "Red"\nmsgstr "Rojo"\n\n'},
        )

    @patch("requests.post")
    def test_parse_query(self, mock_post):
        mock_post.return_value = MockJsonResponse(
            200, {"query": 'name ~ "frank"', "metadata": {"attributes": ["name"]}}
        )
        parsed = get_client().parse_query(self.org.id, "frank")

        self.assertEqual('name ~ "frank"', parsed.query)
        self.assertEqual(["name"], parsed.metadata.attributes)
        mock_post.assert_called_once_with(
            "http://localhost:8090/mr/contact/parse_query",
            headers={"User-Agent": "Temba"},
            json={"query": "frank", "org_id": self.org.id, "parse_only": False},
        )

        mock_post.return_value = MockJsonResponse(400, {"error": "no such field age"})

        with self.assertRaises(RequestException):
            get_client().parse_query(1, "age > 10")

    def test_ticket_assign(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value = MockJsonResponse(200, {"changed_ids": [123]})
            response = get_client().ticket_assign(1, 12, [123, 345], 4)

            self.assertEqual({"changed_ids": [123]}, response)
            mock_post.assert_called_once_with(
                "http://localhost:8090/mr/ticket/assign",
                headers={"User-Agent": "Temba"},
                json={"org_id": 1, "user_id": 12, "ticket_ids": [123, 345], "assignee_id": 4},
            )

    def test_ticket_add_note(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value = MockJsonResponse(200, {"changed_ids": [123]})
            response = get_client().ticket_add_note(1, 12, [123, 345], "please handle")

            self.assertEqual({"changed_ids": [123]}, response)
            mock_post.assert_called_once_with(
                "http://localhost:8090/mr/ticket/add_note",
                headers={"User-Agent": "Temba"},
                json={"org_id": 1, "user_id": 12, "ticket_ids": [123, 345], "note": "please handle"},
            )

    def test_ticket_change_topic(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value = MockJsonResponse(200, {"changed_ids": [123]})
            response = get_client().ticket_change_topic(1, 12, [123, 345], 67)

            self.assertEqual({"changed_ids": [123]}, response)
            mock_post.assert_called_once_with(
                "http://localhost:8090/mr/ticket/change_topic",
                headers={"User-Agent": "Temba"},
                json={"org_id": 1, "user_id": 12, "ticket_ids": [123, 345], "topic_id": 67},
            )

    def test_ticket_close(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value = MockJsonResponse(200, {"changed_ids": [123]})
            response = get_client().ticket_close(1, 12, [123, 345], force=True)

            self.assertEqual({"changed_ids": [123]}, response)
            mock_post.assert_called_once_with(
                "http://localhost:8090/mr/ticket/close",
                headers={"User-Agent": "Temba"},
                json={"org_id": 1, "user_id": 12, "ticket_ids": [123, 345], "force": True},
            )

    def test_ticket_reopen(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value = MockJsonResponse(200, {"changed_ids": [123]})
            response = get_client().ticket_reopen(1, 12, [123, 345])

            self.assertEqual({"changed_ids": [123]}, response)
            mock_post.assert_called_once_with(
                "http://localhost:8090/mr/ticket/reopen",
                headers={"User-Agent": "Temba"},
                json={"org_id": 1, "user_id": 12, "ticket_ids": [123, 345]},
            )

    @patch("requests.post")
    def test_errors(self, mock_post):
        mock_post.return_value = MockJsonResponse(
            422, {"error": "can't create broadcast with no recipients", "code": "broadcast:no_recipients"}
        )

        with self.assertRaises(EmptyBroadcastException) as e:
            get_client().msg_broadcast(1, 2, {}, "eng", [], [], [], "", "", None, None)

        mock_post.return_value = MockJsonResponse(422, {"error": "node isn't valid", "code": "flow:invalid"})

        with self.assertRaises(FlowValidationException) as e:
            get_client().flow_inspect(1, {})

        self.assertEqual("node isn't valid", e.exception.error)
        self.assertEqual("node isn't valid", str(e.exception))

        mock_post.return_value = MockJsonResponse(
            422, {"error": "no such field age", "code": "query:unknown_property", "extra": {"property": "age"}}
        )

        with self.assertRaises(QueryValidationException) as e:
            get_client().contact_search(1, 2, "age > 10", "-created_on")

        self.assertEqual("no such field age", e.exception.error)
        self.assertEqual("unknown_property", e.exception.code)
        self.assertEqual({"property": "age"}, e.exception.extra)
        self.assertEqual("Can't resolve 'age' to a field or URN scheme.", str(e.exception))

        mock_post.return_value = MockJsonResponse(
            422, {"error": "URN 1 is taken", "code": "urn:taken", "extra": {"index": 1}}
        )

        with self.assertRaises(URNValidationException) as e:
            get_client().contact_create(
                1, 2, ContactSpec(name="Bob", language="eng", urns=["tel:+123456789"], fields={}, groups=[])
            )

        self.assertEqual("URN 1 is taken", e.exception.error)
        self.assertEqual("taken", e.exception.code)
        self.assertEqual(1, e.exception.index)
        self.assertEqual("URN 1 is taken", str(e.exception))

        mock_post.return_value = MockJsonResponse(500, {"error": "error loading fields"})

        with self.assertRaises(RequestException) as e:
            get_client().contact_search(1, 2, "age > 10", "-created_on")

        self.assertEqual("error loading fields", e.exception.error)

        mock_post.return_value = MockResponse(502, "Bad Gateway")

        with self.assertRaises(RequestException) as e:
            get_client().contact_search(1, 2, "age > 10", "-created_on")

        self.assertEqual("Bad Gateway", e.exception.error)


class QueryExceptionTest(TembaTest):
    def test_str(self):
        tests = (
            (
                QueryValidationException("mismatched input '$' expecting {'(', TEXT, STRING}", "syntax"),
                "Invalid query syntax.",
            ),
            (
                QueryValidationException("can't convert 'XZ' to a number", "invalid_number", {"value": "XZ"}),
                "Unable to convert 'XZ' to a number.",
            ),
            (
                QueryValidationException("can't convert 'AB' to a date", "invalid_date", {"value": "AB"}),
                "Unable to convert 'AB' to a date.",
            ),
            (
                QueryValidationException(
                    "'Cool Kids' is not a valid group name", "invalid_group", {"value": "Cool Kids"}
                ),
                "'Cool Kids' is not a valid group name.",
            ),
            (
                QueryValidationException(
                    "'zzzzzz' is not a valid language code", "invalid_language", {"value": "zzzz"}
                ),
                "'zzzz' is not a valid language code.",
            ),
            (
                QueryValidationException(
                    "contains operator on name requires token of minimum length 2",
                    "invalid_partial_name",
                    {"min_token_length": "2"},
                ),
                "Using ~ with name requires token of at least 2 characters.",
            ),
            (
                QueryValidationException(
                    "contains operator on URN requires value of minimum length 3",
                    "invalid_partial_urn",
                    {"min_value_length": "3"},
                ),
                "Using ~ with URN requires value of at least 3 characters.",
            ),
            (
                QueryValidationException(
                    "contains conditions can only be used with name or URN values",
                    "unsupported_contains",
                    {"property": "uuid"},
                ),
                "Can only use ~ with name or URN values.",
            ),
            (
                QueryValidationException(
                    "comparisons with > can only be used with date and number fields",
                    "unsupported_comparison",
                    {"property": "uuid", "operator": ">"},
                ),
                "Can only use > with number or date values.",
            ),
            (
                QueryValidationException(
                    "can't check whether 'uuid' is set or not set",
                    "unsupported_setcheck",
                    {"property": "uuid", "operator": "!="},
                ),
                "Can't check whether 'uuid' is set or not set.",
            ),
            (
                QueryValidationException(
                    "can't resolve 'beers' to attribute, scheme or field", "unknown_property", {"property": "beers"}
                ),
                "Can't resolve 'beers' to a field or URN scheme.",
            ),
            (
                QueryValidationException("unknown property type 'xxx'", "unknown_property_type", {"type": "xxx"}),
                "Prefixes must be 'fields' or 'urns'.",
            ),
            (
                QueryValidationException("cannot query on redacted URNs", "redacted_urns", {}),
                "Can't query on URNs in an anonymous workspace.",
            ),
            (QueryValidationException("no code here", "", {}), "no code here"),
        )

        for exception, expected in tests:
            self.assertEqual(expected, str(exception))
