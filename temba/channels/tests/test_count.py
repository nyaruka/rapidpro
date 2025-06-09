from datetime import date, datetime, timezone as tzone

from temba.msgs.models import Msg
from temba.tests import TembaTest

from ..models import ChannelCount
from ..tasks import squash_channel_counts


class ChannelCountTest(TembaTest):
    def test_counts(self):
        contact = self.create_contact("Joe", phone="+250788111222")

        self.assertEqual(0, ChannelCount.objects.count())

        # message without a channel won't be recorded
        self.create_outgoing_msg(contact, "X", failed_reason=Msg.FAILED_NO_DESTINATION)
        self.assertEqual(0, ChannelCount.objects.count())

        # create some messages...
        self.create_incoming_msg(contact, "A", created_on=datetime(2023, 5, 31, 13, 0, 30, 0, tzone.utc))
        self.create_incoming_msg(contact, "B", created_on=datetime(2023, 6, 1, 13, 0, 30, 0, tzone.utc))
        self.create_incoming_msg(contact, "C", created_on=datetime(2023, 6, 1, 13, 0, 30, 0, tzone.utc))
        self.create_incoming_msg(contact, "D", created_on=datetime(2023, 6, 1, 13, 0, 30, 0, tzone.utc), voice=True)
        self.create_outgoing_msg(contact, "E", created_on=datetime(2023, 6, 1, 13, 0, 30, 0, tzone.utc))

        # and 3 in bulk
        Msg.objects.bulk_create(
            [
                Msg(
                    org=self.org,
                    channel=self.channel,
                    contact=contact,
                    text="F",
                    direction="O",
                    msg_type="T",
                    is_android=False,
                    created_on=datetime(2023, 6, 1, 13, 0, 30, 0, tzone.utc),
                    modified_on=datetime(2023, 6, 1, 13, 0, 30, 0, tzone.utc),
                ),
                Msg(
                    org=self.org,
                    channel=self.channel,
                    contact=contact,
                    text="G",
                    direction="O",
                    msg_type="T",
                    is_android=False,
                    created_on=datetime(2023, 6, 1, 13, 0, 30, 0, tzone.utc),
                    modified_on=datetime(2023, 6, 1, 13, 0, 30, 0, tzone.utc),
                ),
                Msg(
                    org=self.org,
                    channel=self.channel,
                    contact=contact,
                    text="H",
                    direction="O",
                    msg_type="V",
                    is_android=False,
                    created_on=datetime(2023, 6, 1, 13, 0, 30, 0, tzone.utc),
                    modified_on=datetime(2023, 6, 1, 13, 0, 30, 0, tzone.utc),
                ),
            ]
        )

        self.assertEqual(
            {
                (date(2023, 5, 31), "text:in"): 1,
                (date(2023, 6, 1), "text:in"): 2,
                (date(2023, 6, 1), "text:out"): 3,
                (date(2023, 6, 1), "voice:in"): 1,
                (date(2023, 6, 1), "voice:out"): 1,
            },
            self.channel.counts.day_totals(scoped=True),
        )

        # squash our counts
        squash_channel_counts()

        self.assertEqual(ChannelCount.objects.all().count(), 5)

        self.assertEqual(
            {
                (date(2023, 5, 31), "text:in"): 1,
                (date(2023, 6, 1), "text:in"): 2,
                (date(2023, 6, 1), "text:out"): 3,
                (date(2023, 6, 1), "voice:in"): 1,
                (date(2023, 6, 1), "voice:out"): 1,
            },
            self.channel.counts.day_totals(scoped=True),
        )

        # soft deleting a message doesn't decrement the count
        Msg.bulk_soft_delete([Msg.objects.get(text="A")])

        self.assertEqual(
            {
                (date(2023, 5, 31), "text:in"): 1,
                (date(2023, 6, 1), "text:in"): 2,
                (date(2023, 6, 1), "text:out"): 3,
                (date(2023, 6, 1), "voice:in"): 1,
                (date(2023, 6, 1), "voice:out"): 1,
            },
            self.channel.counts.day_totals(scoped=True),
        )

        # nor hard deleting
        Msg.bulk_delete([Msg.objects.get(text="B")])

        self.assertEqual(
            {
                (date(2023, 5, 31), "text:in"): 1,
                (date(2023, 6, 1), "text:in"): 2,
                (date(2023, 6, 1), "text:out"): 3,
                (date(2023, 6, 1), "voice:in"): 1,
                (date(2023, 6, 1), "voice:out"): 1,
            },
            self.channel.counts.day_totals(scoped=True),
        )
