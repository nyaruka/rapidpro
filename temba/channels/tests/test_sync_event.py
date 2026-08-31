from datetime import timedelta

from django.utils import timezone

from temba.tests import TembaTest

from ..models import Channel, SyncEvent
from ..tasks import trim_channel_sync_events


class SyncEventTest(TembaTest):
    def test_sync_event_model(self):
        self.sync_event = SyncEvent.create(
            self.channel,
            dict(p_src="AC", p_sts="DIS", p_lvl=80, net="WIFI", pending=[1, 2], retry=[3, 4], cc="RW"),
            [1, 2],
        )
        self.assertEqual(SyncEvent.objects.all().count(), 1)
        self.assertEqual(self.sync_event.get_pending_messages(), [1, 2])
        self.assertEqual(self.sync_event.get_retry_messages(), [3, 4])
        self.assertEqual(self.sync_event.incoming_command_count, 0)

        self.sync_event = SyncEvent.create(
            self.channel,
            dict(p_src="AC", p_sts="DIS", p_lvl=80, net="WIFI", pending=[1, 2], retry=[3, 4], cc="US"),
            [1],
        )
        self.assertEqual(self.sync_event.incoming_command_count, 0)
        self.channel = Channel.objects.get(pk=self.channel.pk)

        # we shouldn't update country once the relayer is claimed
        self.assertEqual("RW", self.channel.country)

    def test_trim_task(self):
        for _ in range(3):
            SyncEvent.create(
                self.channel,
                dict(p_src="AC", p_sts="DIS", p_lvl=80, net="WIFI", pending=[], retry=[], cc="RW"),
                [],
            )

        SyncEvent.objects.all().update(created_on=timezone.now() - timedelta(days=45))

        trim_channel_sync_events()

        # should always leave at least one per channel
        self.assertEqual(1, SyncEvent.objects.all().count())
