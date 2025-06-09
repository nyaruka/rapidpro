from datetime import timedelta

from django.core import mail
from django.utils import timezone

from temba.notifications.tasks import send_notification_emails
from temba.tests import TembaTest, override_brand

from ..tasks import check_android_channels


class ChannelIncidentsTest(TembaTest):
    def test_disconnected(self):
        # set our last seen to a while ago
        self.channel.last_seen = timezone.now() - timedelta(minutes=40)
        self.channel.save(update_fields=("last_seen",))

        with override_brand(emails={"notifications": "support@mybrand.com"}):
            check_android_channels()

            # should have created an incident
            incident = self.org.incidents.get()
            self.assertEqual(self.channel, incident.channel)
            self.assertEqual("channel:disconnected", incident.incident_type)
            self.assertIsNone(incident.ended_on)

            self.assertEqual(1, self.admin.notifications.count())

            notification = self.admin.notifications.get()
            self.assertFalse(notification.is_seen)

            send_notification_emails()

            self.assertEqual(1, len(mail.outbox))
            self.assertEqual("[Nyaruka] Incident: Channel Disconnected", mail.outbox[0].subject)
            self.assertEqual("support@mybrand.com", mail.outbox[0].from_email)

        # call task again
        check_android_channels()

        # still only one incident
        incident = self.org.incidents.get()
        self.assertEqual(1, len(mail.outbox))

        # ok, let's have the channel show up again
        self.channel.last_seen = timezone.now() + timedelta(minutes=5)
        self.channel.save(update_fields=("last_seen",))

        check_android_channels()

        # still only one incident, but it is now ended
        incident = self.org.incidents.get()
        self.assertIsNotNone(incident.ended_on)
