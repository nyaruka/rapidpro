from datetime import timedelta

from django.core import mail
from django.utils import timezone

from temba.orgs.models import Invitation, OrgRole
from temba.orgs.tasks import cleanup_unverified_users, expire_invitations
from temba.tests import TembaTest
from temba.tickets.models import Team
from temba.users.models import User


class InvitationTest(TembaTest):
    def test_model(self):
        invitation = Invitation.create(self.org, self.admin, "invitededitor@textit.com", OrgRole.EDITOR)

        self.assertEqual(OrgRole.EDITOR, invitation.role)

        invitation.send()

        self.assertEqual(1, len(mail.outbox))
        self.assertEqual(["invitededitor@textit.com"], mail.outbox[0].recipients())
        self.assertEqual("[Nyaruka] Invitation to join workspace", mail.outbox[0].subject)
        self.assertIn(f"https://app.rapidpro.io/org/join/{invitation.secret}/", mail.outbox[0].body)

        new_editor = User.create("invitededitor@textit.com", "Bob", "", "Qwerty123", "en-US")
        invitation.accept(new_editor)

        self.assertEqual(1, self.admin.notifications.count())
        self.assertFalse(invitation.is_active)
        self.assertEqual({self.editor, new_editor}, set(self.org.get_users(roles=[OrgRole.EDITOR])))

        # invite an agent user to a specific team
        sales = Team.create(self.org, self.admin, "Sales", topics=[])
        invitation = Invitation.create(self.org, self.admin, "invitedagent@textit.com", OrgRole.AGENT, team=sales)

        self.assertEqual(OrgRole.AGENT, invitation.role)
        self.assertEqual(sales, invitation.team)

        invitation.send()
        new_agent = User.create("invitedagent@textit.com", "Bob", "", "Qwerty123", "en-US")
        invitation.accept(new_agent)

        self.assertEqual({self.agent, new_agent}, set(self.org.get_users(roles=[OrgRole.AGENT])))
        self.assertEqual({new_agent}, set(sales.get_users()))

    def test_expire_task(self):
        invitation1 = Invitation.objects.create(
            org=self.org,
            role_code="E",
            email="neweditor@textit.com",
            created_by=self.admin,
            created_on=timezone.now() - timedelta(days=31),
            modified_by=self.admin,
        )
        invitation2 = Invitation.objects.create(
            org=self.org,
            role_code="T",
            email="newagent@textit.com",
            created_by=self.admin,
            created_on=timezone.now() - timedelta(days=29),
            modified_by=self.admin,
        )

        expire_invitations()

        invitation1.refresh_from_db()
        invitation2.refresh_from_db()

        self.assertFalse(invitation1.is_active)
        self.assertTrue(invitation2.is_active)


class CleanupUnverifiedUsersTest(TembaTest):
    def test_cleanup(self):
        # create an unverified user with no org, joined over 14 days ago
        old_unverified = User.create("spam1@example.com", "Spam", "User", "Qwerty123")
        old_unverified.date_joined = timezone.now() - timedelta(days=15)
        old_unverified.save(update_fields=["date_joined"])

        # create an unverified user with no org, joined less than 14 days ago
        new_unverified = User.create("spam2@example.com", "New", "Spam", "Qwerty123")
        new_unverified.date_joined = timezone.now() - timedelta(days=5)
        new_unverified.save(update_fields=["date_joined"])

        # create a verified user with no org, joined over 14 days ago — should NOT be cleaned up
        verified_no_org = User.create("verified@example.com", "Verified", "User", "Qwerty123")
        verified_no_org.date_joined = timezone.now() - timedelta(days=15)
        verified_no_org.save(update_fields=["date_joined"])
        verified_no_org.set_verified(True)

        # existing admin user has org — should NOT be cleaned up even if unverified
        self.admin.date_joined = timezone.now() - timedelta(days=30)
        self.admin.save(update_fields=["date_joined"])
        self.admin.emailaddress_set.all().delete()

        result = cleanup_unverified_users()

        # only the old unverified user with no org should be released
        old_unverified.refresh_from_db()
        self.assertFalse(old_unverified.is_active)

        new_unverified.refresh_from_db()
        self.assertTrue(new_unverified.is_active)

        verified_no_org.refresh_from_db()
        self.assertTrue(verified_no_org.is_active)

        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

        self.assertEqual(result, {"released": 1})
