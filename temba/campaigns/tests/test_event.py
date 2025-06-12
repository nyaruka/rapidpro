from datetime import datetime, timedelta, timezone as tzone

from django_valkey import get_valkey_connection

from django.utils import timezone

from temba.campaigns.models import Campaign, CampaignEvent
from temba.contacts.models import ContactField, ContactFire
from temba.tests import TembaTest, mock_mailroom
from temba.utils.uuid import uuid4


class CampaignEventTest(TembaTest):
    @mock_mailroom
    def test_model(self, mr_mocks):
        contact1 = self.create_contact("Joe", phone="+1234567890")
        contact2 = self.create_contact("Jose", phone="+593979123456", language="spa")
        farmers = self.create_group("Farmers", [])
        campaign = Campaign.create(self.org, self.admin, Campaign.get_unique_name(self.org, "Reminders"), farmers)
        field = self.create_field("planting_date", "Planting Date", value_type=ContactField.TYPE_DATETIME)
        flow = self.create_flow("Test Flow")

        event1 = CampaignEvent.create_flow_event(
            self.org, self.admin, campaign, field, offset=30, unit="M", flow=flow, delivery_hour=13
        )
        event2 = CampaignEvent.create_message_event(
            self.org,
            self.admin,
            campaign,
            field,
            offset=12,
            unit="H",
            translations={"eng": {"text": "Hello"}, "spa": {"text": "Hola"}},
            base_language="eng",
            delivery_hour=9,
        )
        event3 = CampaignEvent.create_flow_event(
            self.org, self.admin, campaign, field, offset=4, unit="D", flow=flow, delivery_hour=13
        )
        event4 = CampaignEvent.create_message_event(
            self.org,
            self.admin,
            campaign,
            field,
            offset=2,
            unit="W",
            translations={"eng": {"text": "Goodbye"}},
            base_language="eng",
            delivery_hour=9,
        )

        self.assertEqual("R", event1.status)
        self.assertEqual(0, event1.fire_version)
        self.assertEqual(timedelta(minutes=30), event1.get_offset())
        self.assertEqual(f"<Event: id={event1.id} relative_to=planting_date offset=0:30:00>", repr(event1))

        with self.assertRaises(AssertionError):  # can't call get_message on flow event
            event1.get_message(contact1)

        self.assertEqual(timedelta(hours=12), event2.get_offset())
        self.assertEqual({"text": "Hello"}, event2.get_message(contact1))
        self.assertEqual({"text": "Hola"}, event2.get_message(contact2))

        self.assertEqual(timedelta(days=4), event3.get_offset())
        self.assertEqual(timedelta(days=14), event4.get_offset())

    def test_fire_counts(self):
        contact1 = self.create_contact("Ann", phone="+1234567890")
        contact2 = self.create_contact("Bob", phone="+1234567891")
        farmers = self.create_group("Farmers", [contact1, contact2])
        campaign = Campaign.create(self.org, self.admin, "Reminders", farmers)
        planting_date = self.create_field("planting_date", "Planting Date", value_type=ContactField.TYPE_DATETIME)
        event1 = CampaignEvent.create_message_event(
            self.org,
            self.admin,
            campaign,
            planting_date,
            offset=1,
            unit="W",
            translations={"eng": {"text": "1"}},
            base_language="eng",
            delivery_hour=13,
        )
        event2 = CampaignEvent.create_message_event(
            self.org,
            self.admin,
            campaign,
            planting_date,
            offset=3,
            unit="D",
            translations={"eng": {"text": "2"}},
            base_language="eng",
            delivery_hour=9,
        )

        def create_fire(contact, event, fire_version=None):
            return ContactFire.objects.create(
                org=self.org,
                contact=contact,
                fire_type="C",
                scope=f"{event.id}:{fire_version or event.fire_version}",
                fire_on=timezone.now(),
            )

        create_fire(contact1, event1)
        fire2 = create_fire(contact2, event1)
        fire3 = create_fire(contact1, event2)
        create_fire(contact1, event2, fire_version=2)  # not the current version
        ContactFire.objects.create(org=self.org, contact=contact1, fire_type="S", scope="", fire_on=timezone.now())

        self.assertEqual(2, event1.get_fire_count())
        self.assertEqual(1, event2.get_fire_count())

        # can also be prefetched
        events = campaign.get_events().order_by("id")
        campaign.prefetch_fire_counts(events)

        self.assertEqual(2, events[0].get_fire_count())
        self.assertEqual(1, events[1].get_fire_count())

        fire2.delete()
        fire3.delete()

        self.assertEqual(1, event1.get_fire_count())
        self.assertEqual(0, event2.get_fire_count())

    def test_get_recent_fires(self):
        contact1 = self.create_contact("Ann", phone="+1234567890")
        contact2 = self.create_contact("Bob", phone="+1234567891")
        farmers = self.create_group("Farmers", [contact1, contact2])
        campaign = Campaign.create(self.org, self.admin, "Reminders", farmers)
        planting_date = self.create_field("planting_date", "Planting Date", value_type=ContactField.TYPE_DATETIME)
        flow = self.create_flow("Test Flow")
        event1 = CampaignEvent.create_flow_event(
            self.org, self.admin, campaign, planting_date, offset=1, unit="W", flow=flow, delivery_hour=13
        )
        event2 = CampaignEvent.create_message_event(
            self.org,
            self.admin,
            campaign,
            planting_date,
            offset=3,
            unit="D",
            translations={"eng": {"text": "Hello"}},
            base_language="eng",
            delivery_hour=9,
        )

        def add_recent_contact(event, contact, ts: float):
            r = get_valkey_connection()
            member = f"{uuid4()}|{contact.id}"
            r.zadd(f"recent_campaign_fires:{event.id}", mapping={member: ts})

        add_recent_contact(event1, contact1, 1639338554.969123)
        add_recent_contact(event1, contact2, 1639338555.234567)
        add_recent_contact(event2, contact1, 1639338561.345678)

        self.assertEqual(
            [
                {"contact": contact2, "time": datetime(2021, 12, 12, 19, 49, 15, 234567, tzone.utc)},
                {"contact": contact1, "time": datetime(2021, 12, 12, 19, 49, 14, 969123, tzone.utc)},
            ],
            event1.get_recent_fires(),
        )
        self.assertEqual(
            [
                {"contact": contact1, "time": datetime(2021, 12, 12, 19, 49, 21, 345678, tzone.utc)},
            ],
            event2.get_recent_fires(),
        )
