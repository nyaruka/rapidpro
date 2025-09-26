from datetime import timedelta

from django.template import Context
from django.utils import timezone

from temba.msgs.models import Msg
from temba.tests import TembaTest

from .channels import channel_log_link


class ChannelsTest(TembaTest):
    def test_channel_log_link(self):
        flow = self.create_flow("IVR")
        joe = self.create_contact("Joe", phone="+1234567890")
        msg = self.create_incoming_msg(joe, "Hi")
        call = self.create_incoming_call(flow, joe)
        old_msg = self.create_incoming_msg(joe, "Hi", created_on=timezone.now() - timedelta(days=15))
        channel_less_msg = self.create_outgoing_msg(joe, "Submitted", failed_reason=Msg.FAILED_NO_DESTINATION)

        call_logs_url = f"/channels/channel/logs/{self.channel.uuid}/call/{call.uuid}/"
        msg_logs_url = f"/channels/channel/logs/{self.channel.uuid}/msg/{msg.uuid}/"

        # admin user sees links to msg and call logs
        self.assertEqual(
            {"logs_url": call_logs_url}, channel_log_link(Context({"user_org": self.org, "user": self.admin}), call)
        )
        self.assertEqual(
            {"logs_url": msg_logs_url}, channel_log_link(Context({"user_org": self.org, "user": self.admin}), msg)
        )

        # editor user doesn't
        self.assertEqual(
            {"logs_url": None}, channel_log_link(Context({"user_org": self.org, "user": self.editor}), call)
        )
        self.assertEqual(
            {"logs_url": None}, channel_log_link(Context({"user_org": self.org, "user": self.editor}), msg)
        )

        # no log link for channel-less messages or older messages
        self.assertEqual(
            {"logs_url": None}, channel_log_link(Context({"user_org": self.org, "user": self.admin}), channel_less_msg)
        )
        self.assertEqual(
            {"logs_url": None}, channel_log_link(Context({"user_org": self.org, "user": self.admin}), old_msg)
        )
