from datetime import timedelta

from django.utils import timezone

from temba.contacts.models import ContactFire
from temba.flows.models import FlowSession
from temba.tests import MigrationTest
from temba.utils.uuid import uuid4


class CreateSessionExpiresFiresTest(MigrationTest):
    app = "contacts"
    migrate_from = "0204_alter_contactfire_fire_type"
    migrate_to = "0205_create_session_expires_fires"

    def setUpBeforeMigration(self, apps):
        def create_contact_and_sessions(name, phone, current_session_uuid):
            contact = self.create_contact(name, phone=phone, current_session_uuid=current_session_uuid)
            FlowSession.objects.create(
                uuid=uuid4(),
                contact=contact,
                status=FlowSession.STATUS_COMPLETED,
                output_url="http://sessions.com/123.json",
                created_on=timezone.now(),
                ended_on=timezone.now(),
            )
            FlowSession.objects.create(
                uuid=current_session_uuid,
                contact=contact,
                status=FlowSession.STATUS_WAITING,
                output_url="http://sessions.com/123.json",
                created_on=timezone.now(),
            )
            return contact

        # contacts with waiting sessions but no session expiration fire
        self.contact1 = create_contact_and_sessions("Ann", "+1234567001", "a0e707ef-ae06-4e39-a9b1-49eed0273dae")
        self.contact2 = create_contact_and_sessions("Bob", "+1234567002", "4a675e5d-ebc1-4fe7-be74-0450f550f8ee")

        # contact with waiting session and already has a session expiration fire
        self.contact3 = create_contact_and_sessions("Cat", "+1234567003", "a83a82f4-6a25-4662-a8e1-b53ee7d259a2")
        ContactFire.objects.create(
            org=self.org,
            contact=self.contact3,
            fire_type="S",
            scope="",
            fire_on=timezone.now() + timedelta(days=30),
            session_uuid="a83a82f4-6a25-4662-a8e1-b53ee7d259a2",
        )

        # contact with no waiting session
        self.contact4 = self.create_contact("Dan", phone="+1234567004")

    def test_migration(self):
        def assert_session_expire(contact):
            self.assertTrue(contact.fires.exists())

            session = contact.sessions.filter(status="W").get()
            fire = contact.fires.get()

            self.assertEqual(fire.org, contact.org)
            self.assertEqual(fire.fire_type, "S")
            self.assertEqual(fire.scope, "")
            self.assertGreaterEqual(fire.fire_on, session.created_on + timedelta(days=30))
            self.assertLess(fire.fire_on, session.created_on + timedelta(days=31))
            self.assertEqual(fire.session_uuid, session.uuid)

        assert_session_expire(self.contact1)
        assert_session_expire(self.contact2)
        assert_session_expire(self.contact3)

        self.assertFalse(self.contact4.fires.exists())
