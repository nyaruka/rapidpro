from temba.orgs.models import Org
from temba.tests import TembaTest, mock_mailroom

from ..models import Channel, SyncEvent


class SyncEventTest(TembaTest):
    def setUp(self):
        self.user = self.create_user("tito")
        self.org = Org.objects.create(
            name="Temba", timezone="Africa/Kigali", created_by=self.user, modified_by=self.user
        )
        self.tel_channel = Channel.create(
            self.org,
            self.user,
            "RW",
            "A",
            "Test Channel",
            "0785551212",
            secret="12345",
            config={Channel.CONFIG_FCM_ID: "123"},
        )

    @mock_mailroom
    def test_sync_event_model(self, mr_mocks):
        self.sync_event = SyncEvent.create(
            self.tel_channel,
            dict(p_src="AC", p_sts="DIS", p_lvl=80, net="WIFI", pending=[1, 2], retry=[3, 4], cc="RW"),
            [1, 2],
        )
        self.assertEqual(SyncEvent.objects.all().count(), 1)
        self.assertEqual(self.sync_event.get_pending_messages(), [1, 2])
        self.assertEqual(self.sync_event.get_retry_messages(), [3, 4])
        self.assertEqual(self.sync_event.incoming_command_count, 0)

        self.sync_event = SyncEvent.create(
            self.tel_channel,
            dict(p_src="AC", p_sts="DIS", p_lvl=80, net="WIFI", pending=[1, 2], retry=[3, 4], cc="US"),
            [1],
        )
        self.assertEqual(self.sync_event.incoming_command_count, 0)
        self.tel_channel = Channel.objects.get(pk=self.tel_channel.pk)

        # we shouldn't update country once the relayer is claimed
        self.assertEqual("RW", self.tel_channel.country)
