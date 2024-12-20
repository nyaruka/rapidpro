from datetime import timedelta

from django_redis import get_redis_connection
from smartmin.users.models import FailedLogin, RecoveryToken

from django.core import mail
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from temba.orgs.models import Invitation, Org, OrgRole
from temba.orgs.tasks import send_user_verification_email
from temba.tests import CRUDLTestMixin, TembaTest
from temba.tickets.models import Team


class UserCRUDLTest(TembaTest, CRUDLTestMixin):
    def test_list(self):
        list_url = reverse("orgs.user_list")

        system_user = self.create_user("system@textit.com")
        system_user.settings.is_system = True
        system_user.settings.save(update_fields=("is_system",))

        # add system user to workspace
        self.org.add_user(system_user, OrgRole.ADMINISTRATOR)

        # nobody can access if users feature not enabled
        response = self.requestView(list_url, self.admin)
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.org.features = [Org.FEATURE_USERS]
        self.org.save(update_fields=("features",))

        self.assertRequestDisallowed(list_url, [None, self.user, self.editor, self.agent])

        response = self.assertListFetch(
            list_url, [self.admin], context_objects=[self.admin, self.agent, self.editor, self.user]
        )
        self.assertNotContains(response, "(All Topics)")

        self.org.features += [Org.FEATURE_TEAMS]
        self.org.save(update_fields=("features",))

        response = self.assertListFetch(
            list_url, [self.admin], context_objects=[self.admin, self.agent, self.editor, self.user]
        )
        self.assertEqual(response.context["admin_count"], 1)
        self.assertContains(response, "(All Topics)")

        # can search by name or email
        self.assertListFetch(list_url + "?search=andy", [self.admin], context_objects=[self.admin])
        self.assertListFetch(list_url + "?search=editor@textit.com", [self.admin], context_objects=[self.editor])

        response = self.requestView(list_url, self.customer_support, choose_org=self.org)
        self.assertEqual(
            set(list(response.context["object_list"])),
            {self.admin, self.agent, self.editor, self.user, system_user},
        )
        self.assertContains(response, "(All Topics)")
        self.assertEqual(response.context["admin_count"], 2)

    def test_team(self):
        team_url = reverse("orgs.user_team", args=[self.org.default_ticket_team.id])

        # nobody can access if teams feature not enabled
        response = self.requestView(team_url, self.admin)
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.org.features = [Org.FEATURE_TEAMS]
        self.org.save(update_fields=("features",))

        self.assertRequestDisallowed(team_url, [None, self.user, self.editor, self.agent])

        self.assertListFetch(team_url, [self.admin], context_objects=[self.agent])
        self.assertContentMenu(team_url, self.admin, [])  # because it's a system team

        team = Team.create(self.org, self.admin, "My Team")
        team_url = reverse("orgs.user_team", args=[team.id])

        self.assertContentMenu(team_url, self.admin, ["Edit", "Delete"])

    def test_update(self):
        system_user = self.create_user("system@textit.com")
        system_user.settings.is_system = True
        system_user.settings.save(update_fields=("is_system",))

        update_url = reverse("orgs.user_update", args=[self.agent.id])

        # nobody can access if users feature not enabled
        response = self.requestView(update_url, self.admin)
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.org.features = [Org.FEATURE_USERS]
        self.org.save(update_fields=("features",))

        self.assertRequestDisallowed(update_url, [None, self.user, self.editor, self.agent])

        self.assertUpdateFetch(update_url, [self.admin], form_fields={"role": "T"})

        # check can't update user not in the current org
        self.assertRequestDisallowed(reverse("orgs.user_update", args=[self.admin2.id]), [self.admin])

        # role field for viewers defaults to editor
        update_url = reverse("orgs.user_update", args=[self.user.id])

        self.assertUpdateFetch(update_url, [self.admin], form_fields={"role": "E"})

        response = self.assertUpdateSubmit(update_url, self.admin, {"role": "E"})
        self.assertRedirect(response, reverse("orgs.user_list"))

        self.assertEqual({self.user, self.editor}, set(self.org.get_users(roles=[OrgRole.EDITOR])))

        # adding teams feature enables team selection for agents
        self.org.features += [Org.FEATURE_TEAMS]
        self.org.save(update_fields=("features",))
        sales = Team.create(self.org, self.admin, "Sales", topics=[])

        update_url = reverse("orgs.user_update", args=[self.agent.id])

        self.assertUpdateFetch(
            update_url, [self.admin], form_fields={"role": "T", "team": self.org.default_ticket_team}
        )
        self.assertUpdateSubmit(update_url, self.admin, {"role": "T", "team": sales.id})

        self.org._membership_cache = {}
        self.assertEqual(sales, self.org.get_membership(self.agent).team)

        # try updating ourselves...
        update_url = reverse("orgs.user_update", args=[self.admin.id])

        # can't be updated because no other admins
        response = self.assertUpdateSubmit(update_url, self.admin, {"role": "E"}, object_unchanged=self.admin)
        self.assertRedirect(response, reverse("orgs.user_list"))
        self.assertEqual({self.user, self.editor}, set(self.org.get_users(roles=[OrgRole.EDITOR])))
        self.assertEqual({self.admin}, set(self.org.get_users(roles=[OrgRole.ADMINISTRATOR])))

        # even if we add system user to workspace
        self.org.add_user(system_user, OrgRole.ADMINISTRATOR)
        response = self.assertUpdateSubmit(update_url, self.admin, {"role": "E"}, object_unchanged=self.admin)
        self.assertRedirect(response, reverse("orgs.user_list"))
        self.assertEqual({self.user, self.editor}, set(self.org.get_users(roles=[OrgRole.EDITOR])))
        self.assertEqual({self.admin, system_user}, set(self.org.get_users(roles=[OrgRole.ADMINISTRATOR])))

        # add another admin to workspace and try again
        self.org.add_user(self.admin2, OrgRole.ADMINISTRATOR)

        response = self.assertUpdateSubmit(update_url, self.admin, {"role": "E"}, object_unchanged=self.admin)
        self.assertRedirect(response, reverse("orgs.org_start"))  # no longer have access to user list page

        self.assertEqual({self.user, self.editor, self.admin}, set(self.org.get_users(roles=[OrgRole.EDITOR])))
        self.assertEqual({self.admin2, system_user}, set(self.org.get_users(roles=[OrgRole.ADMINISTRATOR])))

        # cannot update system user on a workspace
        update_url = reverse("orgs.user_update", args=[system_user.id])
        response = self.requestView(update_url, self.admin2)
        self.assertRedirect(response, reverse("orgs.org_choose"))
        self.assertEqual({self.user, self.editor, self.admin}, set(self.org.get_users(roles=[OrgRole.EDITOR])))
        self.assertEqual({self.admin2, system_user}, set(self.org.get_users(roles=[OrgRole.ADMINISTRATOR])))

    def test_delete(self):
        system_user = self.create_user("system@textit.com")
        system_user.settings.is_system = True
        system_user.settings.save(update_fields=("is_system",))

        delete_url = reverse("orgs.user_delete", args=[self.agent.id])

        # nobody can access if users feature not enabled
        response = self.requestView(delete_url, self.admin)
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.org.features = [Org.FEATURE_USERS]
        self.org.save(update_fields=("features",))

        self.assertRequestDisallowed(delete_url, [None, self.user, self.editor, self.agent])

        # check can't delete user not in the current org
        self.assertRequestDisallowed(reverse("orgs.user_delete", args=[self.admin2.id]), [self.admin])

        response = self.assertDeleteFetch(delete_url, [self.admin], as_modal=True)
        self.assertContains(
            response, "You are about to remove the user <b>Agnes</b> from your workspace. Are you sure?"
        )

        # submitting the delete doesn't actually delete the user - only removes them from the org
        response = self.assertDeleteSubmit(delete_url, self.admin, object_unchanged=self.agent)

        self.assertRedirect(response, reverse("orgs.user_list"))
        self.assertEqual({self.user, self.editor, self.admin}, set(self.org.get_users()))

        # try deleting ourselves..
        delete_url = reverse("orgs.user_delete", args=[self.admin.id])

        # can't be removed because no other admins
        response = self.assertDeleteSubmit(delete_url, self.admin, object_unchanged=self.admin)
        self.assertRedirect(response, reverse("orgs.user_list"))
        self.assertEqual({self.user, self.editor, self.admin}, set(self.org.get_users()))

        # cannot still even when the other admin is a system user
        self.org.add_user(system_user, OrgRole.ADMINISTRATOR)
        response = self.assertDeleteSubmit(delete_url, self.admin, object_unchanged=self.admin)
        self.assertRedirect(response, reverse("orgs.user_list"))
        self.assertEqual({self.user, self.editor, self.admin, system_user}, set(self.org.get_users()))

        # cannot remove system user too
        self.assertRequestDisallowed(reverse("orgs.user_delete", args=[system_user.id]), [self.admin])
        self.assertEqual({self.user, self.editor, self.admin, system_user}, set(self.org.get_users()))

        # add another admin to workspace and try again
        self.org.add_user(self.admin2, OrgRole.ADMINISTRATOR)

        response = self.assertDeleteSubmit(delete_url, self.admin, object_unchanged=self.admin)

        # this time we could remove ourselves
        response = self.assertDeleteSubmit(delete_url, self.admin, object_unchanged=self.admin)
        self.assertRedirect(response, reverse("orgs.org_choose"))
        self.assertEqual({self.user, self.editor, self.admin2, system_user}, set(self.org.get_users()))

    def test_account(self):
        self.login(self.agent)

        response = self.client.get(reverse("orgs.user_account"))
        self.assertEqual(1, len(response.context["formax"].sections))

        self.login(self.admin)

        response = self.client.get(reverse("orgs.user_account"))
        self.assertEqual(1, len(response.context["formax"].sections))

    def test_edit(self):
        edit_url = reverse("orgs.user_edit")

        # generate a recovery token so we can check it's deleted when email changes
        RecoveryToken.objects.create(user=self.admin, token="1234567")

        # no access if anonymous
        self.assertRequestDisallowed(edit_url, [None])

        self.assertUpdateFetch(
            edit_url,
            [self.admin],
            form_fields=["first_name", "last_name", "email", "avatar", "current_password", "new_password", "language"],
        )

        # language is only shown if there are multiple options
        with override_settings(LANGUAGES=(("en-us", "English"),)):
            self.assertUpdateFetch(
                edit_url,
                [self.admin],
                form_fields=["first_name", "last_name", "email", "avatar", "current_password", "new_password"],
            )

        self.admin.settings.email_status = "V"  # mark user email as verified
        self.admin.settings.email_verification_secret = "old-email-secret"
        self.admin.settings.save()

        # try to submit without required fields
        self.assertUpdateSubmit(
            edit_url,
            self.admin,
            {},
            form_errors={
                "email": "This field is required.",
                "first_name": "This field is required.",
                "last_name": "This field is required.",
                "language": "This field is required.",
                "current_password": "Please enter your password to save changes.",
            },
            object_unchanged=self.admin,
        )

        # change the name and language
        self.assertUpdateSubmit(
            edit_url,
            self.admin,
            {
                "avatar": self.getMockImageUpload(),
                "language": "pt-br",
                "first_name": "Admin",
                "last_name": "User",
                "email": "admin@textit.com",
                "current_password": "",
            },
            success_status=200,
        )

        self.admin.refresh_from_db()
        self.assertEqual("Admin User", self.admin.name)
        self.assertEqual("V", self.admin.settings.email_status)  # unchanged
        self.assertEqual("old-email-secret", self.admin.settings.email_verification_secret)  # unchanged
        self.assertEqual(1, RecoveryToken.objects.filter(user=self.admin).count())  # unchanged
        self.assertIsNotNone(self.admin.settings.avatar)
        self.assertEqual("pt-br", self.admin.settings.language)

        self.assertEqual(0, self.admin.notifications.count())

        self.admin.settings.language = "en-us"
        self.admin.settings.save()

        # try to change email without entering password
        self.assertUpdateSubmit(
            edit_url,
            self.admin,
            {
                "language": "en-us",
                "first_name": "Admin",
                "last_name": "User",
                "email": "admin@trileet.com",
                "current_password": "",
            },
            form_errors={"current_password": "Please enter your password to save changes."},
            object_unchanged=self.admin,
        )

        # submit with current password
        self.assertUpdateSubmit(
            edit_url,
            self.admin,
            {
                "language": "en-us",
                "first_name": "Admin",
                "last_name": "User",
                "email": "admin@trileet.com",
                "current_password": "Qwerty123",
            },
            success_status=200,
        )

        self.admin.refresh_from_db()
        self.admin.settings.refresh_from_db()
        self.assertEqual("admin@trileet.com", self.admin.username)
        self.assertEqual("admin@trileet.com", self.admin.email)
        self.assertEqual("U", self.admin.settings.email_status)  # because email changed
        self.assertNotEqual("old-email-secret", self.admin.settings.email_verification_secret)
        self.assertEqual(0, RecoveryToken.objects.filter(user=self.admin).count())

        # should have a email changed notification using old address
        self.assertEqual({"user:email"}, set(self.admin.notifications.values_list("notification_type", flat=True)))
        self.assertEqual("admin@textit.com", self.admin.notifications.get().email_address)

        # try to change password without entering current password
        self.assertUpdateSubmit(
            edit_url,
            self.admin,
            {
                "language": "en-us",
                "first_name": "Admin",
                "last_name": "User",
                "email": "admin@trileet.com",
                "new_password": "Sesame765",
                "current_password": "",
            },
            form_errors={"current_password": "Please enter your password to save changes."},
            object_unchanged=self.admin,
        )

        # try to change password to something too simple
        self.assertUpdateSubmit(
            edit_url,
            self.admin,
            {
                "language": "en-us",
                "first_name": "Admin",
                "last_name": "User",
                "email": "admin@trileet.com",
                "new_password": "123",
                "current_password": "Qwerty123",
            },
            form_errors={"new_password": "This password is too short. It must contain at least 8 characters."},
            object_unchanged=self.admin,
        )

        # submit with current password
        self.assertUpdateSubmit(
            edit_url,
            self.admin,
            {
                "language": "en-us",
                "first_name": "Admin",
                "last_name": "User",
                "email": "admin@trileet.com",
                "new_password": "Sesame765",
                "current_password": "Qwerty123",
            },
            success_status=200,
        )

        # should have a password changed notification
        self.assertEqual(
            {"user:email", "user:password"}, set(self.admin.notifications.values_list("notification_type", flat=True))
        )

        # check that user still has a valid session
        self.assertEqual(200, self.client.get(reverse("msgs.msg_inbox")).status_code)

        # reset password as test suite assumes this password
        self.admin.set_password("Qwerty123")
        self.admin.save()

        # submit when language isn't an option
        with override_settings(LANGUAGES=(("en-us", "English"),)):
            self.assertUpdateSubmit(
                edit_url,
                self.admin,
                {
                    "first_name": "Andy",
                    "last_name": "Flows",
                    "email": "admin@trileet.com",
                },
                success_status=200,
            )

            self.admin.refresh_from_db()
            self.admin.settings.refresh_from_db()
            self.assertEqual("Andy", self.admin.first_name)
            self.assertEqual("en-us", self.admin.settings.language)

    def test_forget(self):
        forget_url = reverse("orgs.user_forget")

        FailedLogin.objects.create(username="admin@textit.com")
        invitation = Invitation.create(self.org, self.admin, "invited@textit.com", OrgRole.ADMINISTRATOR)

        # no login required to access
        response = self.client.get(forget_url)
        self.assertEqual(200, response.status_code)

        # try submitting email addess that don't exist in the system
        response = self.client.post(forget_url, {"email": "foo@textit.com"})
        self.assertLoginRedirect(response)
        self.assertEqual(0, len(mail.outbox))  # no emails sent

        # try submitting email address that has been invited
        response = self.client.post(forget_url, {"email": "invited@textit.com"})
        self.assertLoginRedirect(response)

        # invitation email should have been resent
        self.assertEqual(1, len(mail.outbox))
        self.assertEqual(["invited@textit.com"], mail.outbox[0].recipients())
        self.assertIn(invitation.secret, mail.outbox[0].body)

        # try submitting email address for existing user
        response = self.client.post(forget_url, {"email": "admin@textit.com"})
        self.assertLoginRedirect(response)

        # will have a recovery token
        token1 = RecoveryToken.objects.get(user=self.admin)

        # and a recovery link email sent
        self.assertEqual(2, len(mail.outbox))
        self.assertEqual(["admin@textit.com"], mail.outbox[1].recipients())
        self.assertIn(token1.token, mail.outbox[1].body)

        # try submitting again for same email address - should error because it's too soon after last one
        response = self.client.post(forget_url, {"email": "admin@textit.com"})
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "A recovery email was already sent to this address recently.")

        # make that token look older and try again
        token1.created_on = timezone.now() - timedelta(minutes=30)
        token1.save(update_fields=("created_on",))

        response = self.client.post(forget_url, {"email": "admin@textit.com"})
        self.assertLoginRedirect(response)

        # will have a new recovery token and the previous one is deleted
        token2 = RecoveryToken.objects.get(user=self.admin)
        self.assertFalse(RecoveryToken.objects.filter(id=token1.id).exists())

        self.assertEqual(3, len(mail.outbox))
        self.assertEqual(["admin@textit.com"], mail.outbox[2].recipients())
        self.assertIn(token2.token, mail.outbox[2].body)

        # failed login records unaffected
        self.assertEqual(1, FailedLogin.objects.filter(username="admin@textit.com").count())

    def test_recover(self):
        recover_url = reverse("orgs.user_recover", args=["1234567890"])

        FailedLogin.objects.create(username="admin@textit.com")
        FailedLogin.objects.create(username="editor@textit.com")

        # 404 if token doesn't exist
        response = self.client.get(recover_url)
        self.assertEqual(404, response.status_code)

        # create token but too old
        token = RecoveryToken.objects.create(
            user=self.admin, token="1234567890", created_on=timezone.now() - timedelta(days=1)
        )

        # user will be redirected to forget password page and told to start again
        response = self.client.get(recover_url)
        self.assertRedirect(response, reverse("orgs.user_forget"))

        token.created_on = timezone.now() - timedelta(minutes=45)
        token.save(update_fields=("created_on",))

        self.assertUpdateFetch(recover_url, [None], form_fields=("new_password", "confirm_password"))

        # try submitting empty form
        self.assertUpdateSubmit(
            recover_url,
            None,
            {},
            form_errors={"new_password": "This field is required.", "confirm_password": "This field is required."},
            object_unchanged=self.admin,
        )

        # try to set password to something too simple
        self.assertUpdateSubmit(
            recover_url,
            None,
            {"new_password": "123", "confirm_password": "123"},
            form_errors={"new_password": "This password is too short. It must contain at least 8 characters."},
            object_unchanged=self.admin,
        )

        # try to set password but confirmation doesn't match
        self.assertUpdateSubmit(
            recover_url,
            None,
            {"new_password": "Qwerty123", "confirm_password": "Azerty123"},
            form_errors={"__all__": "New password and confirmation don't match."},
            object_unchanged=self.admin,
        )

        # on successfull password reset, user is redirected to login page
        response = self.assertUpdateSubmit(
            recover_url, None, {"new_password": "Azerty123", "confirm_password": "Azerty123"}
        )
        self.assertLoginRedirect(response)

        response = self.client.get(response.url)
        self.assertContains(response, "Your password has been updated successfully.")

        # their password has been updated, recovery token deleted and any failed login records deleted
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("Azerty123"))
        self.assertEqual(0, self.admin.recovery_tokens.count())

        self.assertEqual(0, FailedLogin.objects.filter(username="admin@textit.com").count())  # deleted
        self.assertEqual(1, FailedLogin.objects.filter(username="editor@textit.com").count())  # unaffected

    def test_failed(self):
        failed_url = reverse("orgs.user_failed")

        response = self.requestView(failed_url, None)
        self.assertContains(response, "Please wait 10 minutes")

    def test_verify_email(self):
        self.assertEqual(self.admin.settings.email_status, "U")
        self.assertTrue(self.admin.settings.email_verification_secret)

        self.admin.settings.email_verification_secret = "SECRET"
        self.admin.settings.save(update_fields=("email_verification_secret",))

        verify_url = reverse("orgs.user_verify_email", args=["SECRET"])

        # try to access before logging in
        response = self.client.get(verify_url)
        self.assertLoginRedirect(response)

        self.login(self.admin)

        response = self.client.get(reverse("orgs.user_verify_email", args=["WRONG_SECRET"]))
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "This email verification link is invalid.")

        response = self.client.get(verify_url, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "verified successfully")
        self.assertContains(response, reverse("orgs.org_start"))

        self.admin.settings.refresh_from_db()
        self.assertEqual(self.admin.settings.email_status, "V")

        # use the same link again
        response = self.client.get(verify_url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "verified successfully")
        self.assertContains(response, reverse("orgs.org_start"))

        self.login(self.admin2)
        self.assertEqual(self.admin2.settings.email_status, "U")

        # user is told to login as that user
        response = self.client.get(verify_url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "This email verification link is for a different user.")
        self.assertContains(response, reverse("orgs.login"))

        # and isn't verified
        self.admin2.settings.refresh_from_db()
        self.assertEqual(self.admin2.settings.email_status, "U")

    def test_send_verification_email(self):
        r = get_redis_connection()
        send_verification_email_url = reverse("orgs.user_send_verification_email")

        # try to access before logging in
        response = self.client.get(send_verification_email_url)
        self.assertLoginRedirect(response)

        self.login(self.admin)

        response = self.client.get(send_verification_email_url)
        self.assertEqual(405, response.status_code)

        key = f"send_verification_email:{self.admin.email}".lower()

        # simulate haivng the redis key already set
        r.set(key, "1", ex=60 * 10)

        response = self.client.post(send_verification_email_url, {}, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertToast(response, "info", "Verification email already sent. You can retry in 10 minutes.")
        self.assertEqual(0, len(mail.outbox))

        # no email when the redis key is set even with the task itself
        send_user_verification_email.delay(self.org.id, self.admin.id)
        self.assertEqual(0, len(mail.outbox))

        # remove the redis key, as the key expired
        r.delete(key)

        response = self.client.post(send_verification_email_url, {}, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertToast(response, "info", "Verification email sent")

        # and one email sent
        self.assertEqual(1, len(mail.outbox))

        self.admin.settings.email_status = "V"
        self.admin.settings.save(update_fields=("email_status",))

        response = self.client.post(send_verification_email_url, {}, follow=True)
        self.assertEqual(200, response.status_code)

        # no new email sent
        self.assertEqual(1, len(mail.outbox))

        # even the method will not send the email for verified status
        send_user_verification_email.delay(self.org.id, self.admin.id)

        # no new email sent
        self.assertEqual(1, len(mail.outbox))
