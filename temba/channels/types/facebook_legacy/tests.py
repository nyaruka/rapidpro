from unittest.mock import patch

from temba.tests import MockResponse, TembaTest
from temba.triggers.models import Trigger
from temba.utils import json

from ...models import Channel


class FacebookLegacyTypeTest(TembaTest):
    def setUp(self):
        super().setUp()

        self.channel = Channel.create(
            self.org,
            self.admin,
            None,
            "FB",
            name="Facebook",
            address="12345",
            role="SR",
            schemes=["facebook"],
            config={"auth_token": "09876543"},
        )

    @patch("requests.delete")
    def test_release(self, mock_delete):
        mock_delete.return_value = MockResponse(200, json.dumps({"success": True}))
        self.channel.release(self.admin, interrupt=False)

        mock_delete.assert_called_once_with(
            "https://graph.facebook.com/v3.3/me/subscribed_apps", params={"access_token": "09876543"}
        )

    def test_new_conversation_triggers(self):
        flow = self.create_flow("Test")

        with patch("requests.post") as mock_post:
            mock_post.return_value = MockResponse(200, json.dumps({"success": True}))

            trigger = Trigger.create(self.org, self.admin, Trigger.TYPE_NEW_CONVERSATION, flow, channel=self.channel)

            mock_post.assert_called_once_with(
                "https://graph.facebook.com/v3.3/12345/thread_settings",
                json={
                    "setting_type": "call_to_actions",
                    "thread_state": "new_thread",
                    "call_to_actions": [{"payload": "get_started"}],
                },
                headers={"Content-Type": "application/json"},
                params={"access_token": "09876543"},
            )
            mock_post.reset_mock()

            trigger.archive(self.admin)

            mock_post.assert_called_once_with(
                "https://graph.facebook.com/v3.3/12345/thread_settings",
                json={"setting_type": "call_to_actions", "thread_state": "new_thread", "call_to_actions": []},
                headers={"Content-Type": "application/json"},
                params={"access_token": "09876543"},
            )
            mock_post.reset_mock()

            trigger.restore(self.admin)

            mock_post.assert_called_once_with(
                "https://graph.facebook.com/v3.3/12345/thread_settings",
                json={
                    "setting_type": "call_to_actions",
                    "thread_state": "new_thread",
                    "call_to_actions": [{"payload": "get_started"}],
                },
                headers={"Content-Type": "application/json"},
                params={"access_token": "09876543"},
            )
            mock_post.reset_mock()
