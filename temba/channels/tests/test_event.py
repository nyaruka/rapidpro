from datetime import timedelta

from django.utils import timezone

from temba.tests import TembaTest

from ..models import ChannelEvent
from ..tasks import trim_channel_events


class ChannelEventTest(TembaTest):
    def test_trim_task(self):
        contact = self.create_contact("Joe", phone="+250788111222")
        ChannelEvent.objects.create(
            org=self.org,
            channel=self.channel,
            event_type=ChannelEvent.TYPE_STOP_CONTACT,
            contact=contact,
            created_on=timezone.now() - timedelta(days=91),
            occurred_on=timezone.now() - timedelta(days=91),
        )
        e2 = ChannelEvent.objects.create(
            org=self.org,
            channel=self.channel,
            event_type=ChannelEvent.TYPE_NEW_CONVERSATION,
            contact=contact,
            created_on=timezone.now() - timedelta(days=85),
            occurred_on=timezone.now() - timedelta(days=85),
        )

        results = trim_channel_events()
        self.assertEqual({"deleted": 1}, results)

        # should only have one event remaining and should be e2
        self.assertEqual(1, ChannelEvent.objects.all().count())
        self.assertTrue(ChannelEvent.objects.filter(id=e2.id))
