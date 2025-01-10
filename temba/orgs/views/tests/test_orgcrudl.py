import smtplib
from datetime import timezone as tzone
from unittest.mock import patch
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group
from django.core import mail
from django.test.utils import override_settings
from django.urls import reverse

from temba.channels.models import Channel
from temba.contacts.models import URN
from temba.orgs.models import Invitation, Org, OrgRole, User
from temba.tests import CRUDLTestMixin, TembaTest
from temba.utils import languages


class OrgCRUDLTest(TembaTest, CRUDLTestMixin):
    def test_menu(self):
        menu_url = reverse("orgs.org_menu")

        self.child = Org.objects.create(
            name="Child Workspace",
            timezone=ZoneInfo("US/Pacific"),
            flow_languages=["eng"],
            created_by=self.admin,
            modified_by=self.admin,
            parent=self.org,
        )
        self.child.initialize()
        self.child.add_user(self.admin, OrgRole.ADMINISTRATOR)

        self.assertPageMenu(
            menu_url,
            self.admin,
            [
                ("Workspace", ["Nyaruka", "Sign Out", "Child Workspace"]),
                "Messages",
                "Contacts",
                "Flows",
                "Triggers",
                "Campaigns",
                "Tickets",
                ("Notifications", []),
                "Settings",
            ],
            choose_org=self.org,
        )
        self.assertPageMenu(
            f"{menu_url}settings/",
            self.admin,
            [
                "Nyaruka",
                "Account",
                "Resthooks",
                "Incidents",
                "Export",
                "Import",
                ("Channels", ["New Channel", "Test Channel"]),
                ("Classifiers", ["New Classifier"]),
                ("Archives", ["Messages", "Flow Runs"]),
            ],
            choose_org=self.org,
        )

        # agents should only see tickets and settings
        self.assertPageMenu(
            menu_url,
            self.agent,
            [
                ("Workspace", ["Nyaruka", "Sign Out"]),
                "Tickets",
                ("Notifications", []),
                "Settings",
            ],
        )

        # staff without an org on have the staff section
        self.assertPageMenu(menu_url, self.customer_support, ["Staff"])

        self.assertPageMenu(f"{menu_url}staff/", self.customer_support, ["Workspaces", "Users"])

        # if our org has new orgs but not child orgs, we should have a New Workspace button in the menu
        self.org.features = [Org.FEATURE_NEW_ORGS]
        self.org.save()

        self.assertPageMenu(
            menu_url,
            self.admin,
            [
                ("Workspace", ["Nyaruka", "Sign Out", "Child Workspace", "New Workspace"]),
                "Messages",
                "Contacts",
                "Flows",
                "Triggers",
                "Campaigns",
                "Tickets",
                ("Notifications", []),
                "Settings",
            ],
            choose_org=self.org,
        )

        # confirm no notifications
        self.login(self.admin)
        menu = self.client.get(menu_url).json()["results"]
        self.assertEqual(None, menu[8].get("bubble"))

        # flag our org to create a notification
        self.org.flag()
        menu = self.client.get(menu_url).json()["results"]
        self.assertEqual("tomato", menu[8]["bubble"])

    def test_workspace(self):
        workspace_url = reverse("orgs.org_workspace")

        self.assertRequestDisallowed(workspace_url, [None, self.agent])
        response = self.assertListFetch(workspace_url, [self.user, self.editor, self.admin])

        # make sure we have the appropriate number of sections
        self.assertEqual(6, len(response.context["formax"].sections))

        self.assertPageMenu(
            f"{reverse('orgs.org_menu')}settings/",
            self.admin,
            [
                "Nyaruka",
                "Account",
                "Resthooks",
                "Incidents",
                "Export",
                "Import",
                ("Channels", ["New Channel", "Test Channel"]),
                ("Classifiers", ["New Classifier"]),
                ("Archives", ["Messages", "Flow Runs"]),
            ],
        )

        # enable child workspaces, users and teams
        self.org.features = [Org.FEATURE_USERS, Org.FEATURE_CHILD_ORGS, Org.FEATURE_TEAMS]
        self.org.save(update_fields=("features",))

        self.child_org = Org.objects.create(
            name="Child Org",
            timezone=ZoneInfo("Africa/Kigali"),
            location=self.org.location,
            created_by=self.user,
            modified_by=self.user,
            parent=self.org,
        )

        with self.assertNumQueries(9):
            response = self.client.get(workspace_url)

        # should have an extra menu options for workspaces and users
        self.assertPageMenu(
            f"{reverse('orgs.org_menu')}settings/",
            self.admin,
            [
                "Nyaruka",
                "Account",
                "Resthooks",
                "Incidents",
                "Workspaces (2)",
                "Dashboard",
                "Users (4)",
                "Invitations (0)",
                "Teams (1)",
                "Export",
                "Import",
                ("Channels", ["New Channel", "Test Channel"]),
                ("Classifiers", ["New Classifier"]),
                ("Archives", ["Messages", "Flow Runs"]),
            ],
        )

    def test_flow_smtp(self):
        self.login(self.admin)

        settings_url = reverse("orgs.org_workspace")
        config_url = reverse("orgs.org_flow_smtp")

        # orgs without SMTP settings see default from address
        response = self.client.get(settings_url)
        self.assertContains(response, "Emails sent from flows will be sent from <b>no-reply@temba.io</b>.")
        self.assertEqual("no-reply@temba.io", response.context["from_email_default"])  # from settings
        self.assertEqual(None, response.context["from_email_custom"])

        # make org a child to a parent that alsos doesn't have SMTP settings
        self.org.parent = self.org2
        self.org.save(update_fields=("parent",))

        response = self.client.get(config_url)
        self.assertContains(response, "You can add your own SMTP settings for emails sent from flows.")
        self.assertEqual("no-reply@temba.io", response.context["from_email_default"])
        self.assertIsNone(response.context["from_email_custom"])

        # give parent custom SMTP settings
        self.org2.flow_smtp = "smtp://bob%40acme.com:secret@example.com/?from=bob%40acme.com&tls=true"
        self.org2.save(update_fields=("flow_smtp",))

        response = self.client.get(settings_url)
        self.assertContains(response, "Emails sent from flows will be sent from <b>bob@acme.com</b>.")

        response = self.client.get(config_url)
        self.assertContains(response, "You can add your own SMTP settings for emails sent from flows.")
        self.assertEqual("bob@acme.com", response.context["from_email_default"])
        self.assertIsNone(response.context["from_email_custom"])

        # try submitting without any data
        response = self.client.post(config_url, {})
        self.assertFormError(response.context["form"], "from_email", "This field is required.")
        self.assertFormError(response.context["form"], "host", "This field is required.")
        self.assertFormError(response.context["form"], "username", "This field is required.")
        self.assertFormError(response.context["form"], "password", "This field is required.")
        self.assertFormError(response.context["form"], "port", "This field is required.")
        self.assertEqual(len(mail.outbox), 0)

        # try submitting an invalid from address
        response = self.client.post(config_url, {"from_email": "foobar.com"})
        self.assertFormError(response.context["form"], "from_email", "Not a valid email address.")
        self.assertEqual(len(mail.outbox), 0)

        # mock email sending so test send fails
        with patch("temba.utils.email.send.send_email") as mock_send:
            mock_send.side_effect = smtplib.SMTPException("boom")

            response = self.client.post(
                config_url,
                {
                    "from_email": "foo@bar.com",
                    "host": "smtp.example.com",
                    "username": "support@example.com",
                    "password": "secret",
                    "port": "465",
                },
            )
            self.assertFormError(response.context["form"], None, "SMTP settings test failed with error: boom")
            self.assertEqual(len(mail.outbox), 0)

            mock_send.side_effect = Exception("Unexpected Error")
            response = self.client.post(
                config_url,
                {
                    "from_email": "foo@bar.com",
                    "host": "smtp.example.com",
                    "username": "support@example.com",
                    "password": "secret",
                    "port": "465",
                },
                follow=True,
            )
            self.assertFormError(response.context["form"], None, "SMTP settings test failed.")
            self.assertEqual(len(mail.outbox), 0)

        # submit with valid fields
        self.client.post(
            config_url,
            {
                "from_email": "  foo@bar.com  ",  # check trimming
                "host": "smtp.example.com",
                "username": "support@example.com",
                "password": " secret ",
                "port": "465",
            },
        )
        self.assertEqual(len(mail.outbox), 1)

        self.org.refresh_from_db()
        self.assertEqual(
            r"smtp://support%40example.com:secret@smtp.example.com:465/?from=foo%40bar.com&tls=true", self.org.flow_smtp
        )

        response = self.client.get(settings_url)
        self.assertContains(response, "Emails sent from flows will be sent from <b>foo@bar.com</b>.")

        response = self.client.get(config_url)
        self.assertContains(response, "If you no longer want to use these SMTP settings")
        self.assertEqual("bob@acme.com", response.context["from_email_default"])
        self.assertEqual("foo@bar.com", response.context["from_email_custom"])

        # submit with disconnect flag
        self.client.post(config_url, {"disconnect": "true"})

        self.org.refresh_from_db()
        self.assertIsNone(self.org.flow_smtp)

        response = self.client.get(settings_url)
        self.assertContains(response, "Emails sent from flows will be sent from <b>bob@acme.com</b>.")

    def test_join(self):
        # if invitation secret is invalid, redirect to root
        response = self.client.get(reverse("orgs.org_join", args=["invalid"]))
        self.assertRedirect(response, reverse("public.public_index"))

        invitation = Invitation.create(self.org, self.admin, "edwin@textit.com", OrgRole.EDITOR)

        join_url = reverse("orgs.org_join", args=[invitation.secret])
        join_signup_url = reverse("orgs.org_join_signup", args=[invitation.secret])
        join_accept_url = reverse("orgs.org_join_accept", args=[invitation.secret])

        # if no user exists then we redirect to the join signup page
        response = self.client.get(join_url)
        self.assertRedirect(response, join_signup_url)

        user = self.create_user("edwin@textit.com")
        self.login(user)

        response = self.client.get(join_url)
        self.assertRedirect(response, join_accept_url)

        # but only if they're the currently logged in user
        self.login(self.admin)

        response = self.client.get(join_url)
        self.assertContains(response, "Sign in to join the <b>Nyaruka</b> workspace")
        self.assertContains(response, f"/users/login/?next={join_accept_url}")

        # should be logged out as the other user
        self.assertEqual(0, len(self.client.session.keys()))

        # invitation with mismatching case email
        invitation2 = Invitation.create(self.org2, self.admin, "eDwin@textit.com", OrgRole.EDITOR)

        join_accept_url = reverse("orgs.org_join_accept", args=[invitation2.secret])
        join_url = reverse("orgs.org_join", args=[invitation2.secret])

        self.login(user)

        response = self.client.get(join_url)
        self.assertRedirect(response, join_accept_url)

        # but only if they're the currently logged in user
        self.login(self.admin)

        response = self.client.get(join_url)
        self.assertContains(response, "Sign in to join the <b>Trileet Inc.</b> workspace")
        self.assertContains(response, f"/users/login/?next={join_accept_url}")

    def test_join_signup(self):
        # if invitation secret is invalid, redirect to root
        response = self.client.get(reverse("orgs.org_join_signup", args=["invalid"]))
        self.assertRedirect(response, reverse("public.public_index"))

        invitation = Invitation.create(self.org, self.admin, "administrator@trileet.com", OrgRole.ADMINISTRATOR)

        join_signup_url = reverse("orgs.org_join_signup", args=[invitation.secret])
        join_url = reverse("orgs.org_join", args=[invitation.secret])

        # if user already exists then we redirect back to join
        response = self.client.get(join_signup_url)
        self.assertRedirect(response, join_url)

        invitation = Invitation.create(self.org, self.admin, "edwin@textit.com", OrgRole.EDITOR)

        join_signup_url = reverse("orgs.org_join_signup", args=[invitation.secret])
        join_url = reverse("orgs.org_join", args=[invitation.secret])

        response = self.client.get(join_signup_url)
        self.assertContains(response, "edwin@textit.com")
        self.assertEqual(["first_name", "last_name", "password", "loc"], list(response.context["form"].fields.keys()))

        response = self.client.post(join_signup_url, {})
        self.assertFormError(response.context["form"], "first_name", "This field is required.")
        self.assertFormError(response.context["form"], "last_name", "This field is required.")
        self.assertFormError(response.context["form"], "password", "This field is required.")

        response = self.client.post(join_signup_url, {"first_name": "Ed", "last_name": "Edits", "password": "Flows123"})
        self.assertRedirect(response, "/org/start/")

        invitation.refresh_from_db()
        self.assertFalse(invitation.is_active)

        self.assertEqual(1, self.admin.notifications.filter(notification_type="invitation:accepted").count())
        self.assertEqual(2, self.org.get_users(roles=[OrgRole.EDITOR]).count())

    def test_join_accept(self):
        # only authenticated users can access page
        response = self.client.get(reverse("orgs.org_join_accept", args=["invalid"]))
        self.assertLoginRedirect(response)

        # if invitation secret is invalid, redirect to root
        self.login(self.admin)
        response = self.client.get(reverse("orgs.org_join_accept", args=["invalid"]))
        self.assertRedirect(response, reverse("public.public_index"))

        invitation = Invitation.create(self.org, self.admin, "edwin@textit.com", OrgRole.EDITOR)

        join_accept_url = reverse("orgs.org_join_accept", args=[invitation.secret])
        join_url = reverse("orgs.org_join", args=[invitation.secret])

        # if user doesn't exist then redirect back to join
        response = self.client.get(join_accept_url)
        self.assertRedirect(response, join_url)

        user = self.create_user("edwin@textit.com")

        # if user exists but we're logged in as other user, also redirect
        response = self.client.get(join_accept_url)
        self.assertRedirect(response, join_url)

        self.login(user)

        response = self.client.get(join_accept_url)
        self.assertContains(response, "You have been invited to join the <b>Nyaruka</b> workspace.")

        response = self.client.post(join_accept_url)
        self.assertRedirect(response, "/org/start/")

        invitation.refresh_from_db()
        self.assertFalse(invitation.is_active)

        self.assertEqual(1, self.admin.notifications.filter(notification_type="invitation:accepted").count())
        self.assertEqual(2, self.org.get_users(roles=[OrgRole.EDITOR]).count())

    def test_org_grant(self):
        grant_url = reverse("orgs.org_grant")
        response = self.client.get(grant_url)
        self.assertRedirect(response, "/users/login/")

        self.user = self.create_user("tito@textit.com")

        self.login(self.user)
        response = self.client.get(grant_url)
        self.assertRedirect(response, "/users/login/")

        granters = Group.objects.get(name="Granters")
        self.user.groups.add(granters)

        response = self.client.get(grant_url)
        self.assertEqual(200, response.status_code)

        # fill out the form
        post_data = dict(
            email="john@carmack.com",
            first_name="John",
            last_name="Carmack",
            name="Oculus",
            timezone="Africa/Kigali",
            credits="100000",
            password="dukenukem",
        )
        response = self.client.post(grant_url, post_data, follow=True)
        self.assertToast(response, "info", "Workspace successfully created.")

        org = Org.objects.get(name="Oculus")
        self.assertEqual(org.date_format, Org.DATE_FORMAT_DAY_FIRST)

        # check user exists and is admin
        self.assertEqual(OrgRole.ADMINISTRATOR, org.get_user_role(User.objects.get(username="john@carmack.com")))
        self.assertEqual(OrgRole.ADMINISTRATOR, org.get_user_role(User.objects.get(username="tito@textit.com")))

        # try a new org with a user that already exists instead
        del post_data["password"]
        post_data["name"] = "id Software"

        response = self.client.post(grant_url, post_data, follow=True)
        self.assertToast(response, "info", "Workspace successfully created.")

        org = Org.objects.get(name="id Software")
        self.assertEqual(org.date_format, Org.DATE_FORMAT_DAY_FIRST)

        self.assertEqual(OrgRole.ADMINISTRATOR, org.get_user_role(User.objects.get(username="john@carmack.com")))
        self.assertEqual(OrgRole.ADMINISTRATOR, org.get_user_role(User.objects.get(username="tito@textit.com")))

        # try a new org with US timezone
        post_data["name"] = "Bulls"
        post_data["timezone"] = "America/Chicago"
        response = self.client.post(grant_url, post_data, follow=True)

        self.assertToast(response, "info", "Workspace successfully created.")

        org = Org.objects.get(name="Bulls")
        self.assertEqual(Org.DATE_FORMAT_MONTH_FIRST, org.date_format)
        self.assertEqual("en-us", org.language)
        self.assertEqual(["eng"], org.flow_languages)

    def test_org_grant_invalid_form(self):
        grant_url = reverse("orgs.org_grant")

        granters = Group.objects.get(name="Granters")
        self.admin.groups.add(granters)

        self.login(self.admin)

        post_data = dict(
            email="",
            first_name="John",
            last_name="Carmack",
            name="Oculus",
            timezone="Africa/Kigali",
            credits="100000",
            password="dukenukem",
        )
        response = self.client.post(grant_url, post_data)
        self.assertFormError(response.context["form"], "email", "This field is required.")

        post_data = dict(
            email="this-is-not-a-valid-email",
            first_name="John",
            last_name="Carmack",
            name="Oculus",
            timezone="Africa/Kigali",
            credits="100000",
            password="dukenukem",
        )
        response = self.client.post(grant_url, post_data)
        self.assertFormError(response.context["form"], "email", "Enter a valid email address.")

        response = self.client.post(
            grant_url,
            {
                "email": f"john@{'x' * 150}.com",
                "first_name": f"John@{'n' * 150}.com",
                "last_name": f"Carmack@{'k' * 150}.com",
                "name": f"Oculus{'s' * 130}",
                "timezone": "Africa/Kigali",
                "credits": "100000",
                "password": "dukenukem",
            },
        )
        self.assertFormError(
            response.context["form"], "first_name", "Ensure this value has at most 150 characters (it has 159)."
        )
        self.assertFormError(
            response.context["form"], "last_name", "Ensure this value has at most 150 characters (it has 162)."
        )
        self.assertFormError(
            response.context["form"], "name", "Ensure this value has at most 128 characters (it has 136)."
        )
        self.assertFormError(
            response.context["form"],
            "email",
            ["Enter a valid email address.", "Ensure this value has at most 150 characters (it has 159)."],
        )

    def test_org_grant_form_clean(self):
        grant_url = reverse("orgs.org_grant")

        granters = Group.objects.get(name="Granters")
        self.admin.groups.add(granters)

        self.login(self.admin)

        # user with email admin@textit.com already exists and we set a password
        response = self.client.post(
            grant_url,
            {
                "email": "admin@textit.com",
                "first_name": "John",
                "last_name": "Carmack",
                "name": "Oculus",
                "timezone": "Africa/Kigali",
                "credits": "100000",
                "password": "password",
            },
        )
        self.assertFormError(response.context["form"], None, "Login already exists, please do not include password.")

        # try to create a new user with empty password
        response = self.client.post(
            grant_url,
            {
                "email": "a_new_user@textit.com",
                "first_name": "John",
                "last_name": "Carmack",
                "name": "Oculus",
                "timezone": "Africa/Kigali",
                "credits": "100000",
                "password": "",
            },
        )
        self.assertFormError(response.context["form"], None, "Password required for new login.")

        # try to create a new user with invalid password
        response = self.client.post(
            grant_url,
            {
                "email": "a_new_user@textit.com",
                "first_name": "John",
                "last_name": "Carmack",
                "name": "Oculus",
                "timezone": "Africa/Kigali",
                "credits": "100000",
                "password": "pass",
            },
        )
        self.assertFormError(
            response.context["form"], None, "This password is too short. It must contain at least 8 characters."
        )

    @patch("temba.orgs.views.OrgCRUDL.Signup.pre_process")
    def test_new_signup_with_user_logged_in(self, mock_pre_process):
        mock_pre_process.return_value = None
        signup_url = reverse("orgs.org_signup")
        self.user = self.create_user("tito@textit.com")

        self.login(self.user)

        response = self.client.get(signup_url)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            signup_url,
            {
                "first_name": "Kellan",
                "last_name": "Alexander",
                "email": "kellan@example.com",
                "password": "HeyThere123",
                "name": "AlexCom",
                "timezone": "Africa/Kigali",
            },
        )
        self.assertEqual(response.status_code, 302)

        # should have a new user
        user = User.objects.get(username="kellan@example.com")
        self.assertEqual(user.first_name, "Kellan")
        self.assertEqual(user.last_name, "Alexander")
        self.assertEqual(user.email, "kellan@example.com")
        self.assertTrue(user.check_password("HeyThere123"))

        # should have a new org
        org = Org.objects.get(name="AlexCom")
        self.assertEqual(org.timezone, ZoneInfo("Africa/Kigali"))

        # of which our user is an administrator
        self.assertIn(user, org.get_admins())

        # not the logged in user at the signup time
        self.assertNotIn(self.user, org.get_admins())

    @override_settings(
        AUTH_PASSWORD_VALIDATORS=[
            {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
            {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
            {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
        ]
    )
    def test_signup(self):
        signup_url = reverse("orgs.org_signup")
        edit_url = reverse("orgs.user_edit")

        response = self.client.get(signup_url + "?%s" % urlencode({"email": "address@example.com"}))
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].fields)
        self.assertEqual(response.context["view"].derive_initial()["email"], "address@example.com")

        response = self.client.get(signup_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["form"].fields)

        # submit with missing fields
        response = self.client.post(signup_url, {})
        self.assertFormError(response.context["form"], "name", "This field is required.")
        self.assertFormError(response.context["form"], "first_name", "This field is required.")
        self.assertFormError(response.context["form"], "last_name", "This field is required.")
        self.assertFormError(response.context["form"], "email", "This field is required.")
        self.assertFormError(response.context["form"], "password", "This field is required.")
        self.assertFormError(response.context["form"], "timezone", "This field is required.")

        # submit with invalid password and email
        response = self.client.post(
            signup_url,
            {
                "first_name": "Eugene",
                "last_name": "Rwagasore",
                "email": "bad_email",
                "password": "badpass",
                "name": "Your Face",
                "timezone": "Africa/Kigali",
            },
        )
        self.assertFormError(response.context["form"], "email", "Enter a valid email address.")
        self.assertFormError(
            response.context["form"], "password", "This password is too short. It must contain at least 8 characters."
        )

        # submit with password that is too common
        response = self.client.post(
            signup_url,
            {
                "first_name": "Eugene",
                "last_name": "Rwagasore",
                "email": "eugene@temba.io",
                "password": "password",
                "name": "Your Face",
                "timezone": "Africa/Kigali",
            },
        )
        self.assertFormError(response.context["form"], "password", "This password is too common.")

        # submit with password that is all numerical
        response = self.client.post(
            signup_url,
            {
                "first_name": "Eugene",
                "last_name": "Rwagasore",
                "email": "eugene@temba.io",
                "password": "3464357358532",
                "name": "Your Face",
                "timezone": "Africa/Kigali",
            },
        )
        self.assertFormError(response.context["form"], "password", "This password is entirely numeric.")

        # submit with valid data (long email)
        response = self.client.post(
            signup_url,
            {
                "first_name": "Eugene",
                "last_name": "Rwagasore",
                "email": "myal12345678901234567890@relieves.org",
                "password": "HelloWorld1",
                "name": "Relieves World",
                "timezone": "Africa/Kigali",
            },
        )
        self.assertEqual(response.status_code, 302)

        # should have a new user
        user = User.objects.get(username="myal12345678901234567890@relieves.org")
        self.assertEqual(user.first_name, "Eugene")
        self.assertEqual(user.last_name, "Rwagasore")
        self.assertEqual(user.email, "myal12345678901234567890@relieves.org")
        self.assertTrue(user.check_password("HelloWorld1"))

        # should have a new org
        org = Org.objects.get(name="Relieves World")
        self.assertEqual(org.timezone, ZoneInfo("Africa/Kigali"))
        self.assertEqual(str(org), "Relieves World")

        # of which our user is an administrator
        self.assertIn(user, org.get_admins())

        # check default org content was created correctly
        system_fields = set(org.fields.filter(is_system=True).values_list("key", flat=True))
        system_groups = set(org.groups.filter(is_system=True).values_list("name", flat=True))
        sample_flows = set(org.flows.values_list("name", flat=True))

        self.assertEqual({"created_on", "last_seen_on"}, system_fields)
        self.assertEqual({"\\Active", "\\Archived", "\\Blocked", "\\Stopped", "Open Tickets"}, system_groups)
        self.assertEqual(
            {"Sample Flow - Order Status Checker", "Sample Flow - Satisfaction Survey", "Sample Flow - Simple Poll"},
            sample_flows,
        )

        # should now be able to go to channels page
        response = self.client.get(reverse("channels.channel_claim"))
        self.assertEqual(200, response.status_code)

        # can't signup again with same email
        response = self.client.post(
            signup_url,
            {
                "first_name": "Eugene",
                "last_name": "Rwagasore",
                "email": "myal12345678901234567890@relieves.org",
                "password": "HelloWorld1",
                "name": "Relieves World 2",
                "timezone": "Africa/Kigali",
            },
        )
        self.assertFormError(response.context["form"], "email", "That email address is already used")

        # if we hit /login we'll be taken back to the channel page
        response = self.client.get(reverse("orgs.check_login"))
        self.assertRedirect(response, reverse("orgs.org_choose"))

        # but if we log out, same thing takes us to the login page
        self.client.logout()

        response = self.client.get(reverse("orgs.check_login"))
        self.assertLoginRedirect(response)

        # try going to the org home page, no dice
        response = self.client.get(reverse("orgs.org_workspace"))
        self.assertLoginRedirect(response)

        # log in as the user
        self.client.login(username="myal12345678901234567890@relieves.org", password="HelloWorld1")
        response = self.client.get(reverse("orgs.org_workspace"))

        self.assertEqual(200, response.status_code)

        # try changing our username, wrong password
        response = self.client.post(edit_url, {"email": "myal@wr.org", "current_password": "HelloWorld"})
        self.assertEqual(200, response.status_code)
        self.assertFormError(
            response.context["form"],
            "current_password",
            "Please enter your password to save changes.",
        )

        # bad new password
        response = self.client.post(
            edit_url, {"email": "myal@wr.org", "current_password": "HelloWorld1", "new_password": "passwor"}
        )
        self.assertEqual(200, response.status_code)
        self.assertFormError(
            response.context["form"],
            "new_password",
            "This password is too short. It must contain at least 8 characters.",
        )

        User.objects.create(username="bill@msn.com", email="bill@msn.com")

        # dupe user
        response = self.client.post(edit_url, {"email": "bill@MSN.com", "current_password": "HelloWorld1"})
        self.assertEqual(200, response.status_code)
        self.assertFormError(response.context["form"], "email", "Sorry, that email address is already taken.")

        post_data = dict(
            email="myal@wr.org",
            first_name="Myal",
            last_name="Greene",
            language="en-us",
            current_password="HelloWorld1",
        )
        response = self.client.post(edit_url, post_data, HTTP_X_FORMAX=True)
        self.assertEqual(200, response.status_code)

        self.assertTrue(User.objects.get(username="myal@wr.org"))
        self.assertTrue(User.objects.get(email="myal@wr.org"))
        self.assertFalse(User.objects.filter(username="myal@relieves.org"))
        self.assertFalse(User.objects.filter(email="myal@relieves.org"))

    def test_create_new(self):
        create_url = reverse("orgs.org_create")

        # nobody can access if new orgs feature not enabled
        response = self.requestView(create_url, self.admin)
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.org.features = [Org.FEATURE_NEW_ORGS]
        self.org.save(update_fields=("features",))

        # since we can only create new orgs, we don't show type as an option
        self.assertRequestDisallowed(create_url, [None, self.user, self.editor, self.agent])
        self.assertCreateFetch(create_url, [self.admin], form_fields=["name", "timezone"])

        # try to submit an empty form
        response = self.assertCreateSubmit(
            create_url,
            self.admin,
            {},
            form_errors={"name": "This field is required.", "timezone": "This field is required."},
        )

        # submit with valid values to create a new org...
        response = self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "My Other Org", "timezone": "Africa/Nairobi"},
            new_obj_query=Org.objects.filter(name="My Other Org", parent=None),
        )

        new_org = Org.objects.get(name="My Other Org")
        self.assertEqual([], new_org.features)
        self.assertEqual("Africa/Nairobi", str(new_org.timezone))
        self.assertEqual(OrgRole.ADMINISTRATOR, new_org.get_user_role(self.admin))

        # should be now logged into that org
        self.assertRedirect(response, "/org/start/")
        response = self.client.get("/org/start/")
        self.assertEqual(str(new_org.id), response.headers["X-Temba-Org"])

    def test_create_child(self):
        list_url = reverse("orgs.org_list")
        create_url = reverse("orgs.org_create")

        # nobody can access if child orgs feature not enabled
        response = self.requestView(create_url, self.admin)
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.org.features = [Org.FEATURE_CHILD_ORGS]
        self.org.save(update_fields=("features",))

        response = self.client.get(list_url)
        self.assertContentMenu(list_url, self.admin, ["New"])

        # give org2 the same feature
        self.org2.features = [Org.FEATURE_CHILD_ORGS]
        self.org2.save(update_fields=("features",))

        # since we can only create child orgs, we don't show type as an option
        self.assertRequestDisallowed(create_url, [None, self.user, self.editor, self.agent])
        self.assertCreateFetch(create_url, [self.admin], form_fields=["name", "timezone"])

        # try to submit an empty form
        response = self.assertCreateSubmit(
            create_url,
            self.admin,
            {},
            form_errors={"name": "This field is required.", "timezone": "This field is required."},
        )

        # submit with valid values to create a child org...
        response = self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "My Child Org", "timezone": "Africa/Nairobi"},
            new_obj_query=Org.objects.filter(name="My Child Org", parent=self.org),
        )

        child_org = Org.objects.get(name="My Child Org")
        self.assertEqual([], child_org.features)
        self.assertEqual("Africa/Nairobi", str(child_org.timezone))
        self.assertEqual(OrgRole.ADMINISTRATOR, child_org.get_user_role(self.admin))

        # should have been redirected to child management page
        self.assertRedirect(response, "/org/")

    def test_create_child_or_new(self):
        create_url = reverse("orgs.org_create")

        self.login(self.admin)

        self.org.features = [Org.FEATURE_NEW_ORGS, Org.FEATURE_CHILD_ORGS]
        self.org.save(update_fields=("features",))

        # give org2 the same feature
        self.org2.features = [Org.FEATURE_NEW_ORGS, Org.FEATURE_CHILD_ORGS]
        self.org2.save(update_fields=("features",))

        # because we can create both new orgs and child orgs, type is an option
        self.assertRequestDisallowed(create_url, [None, self.user, self.editor, self.agent])
        self.assertCreateFetch(create_url, [self.admin], form_fields=["type", "name", "timezone"])

        # create new org
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"type": "new", "name": "New Org", "timezone": "Africa/Nairobi"},
            new_obj_query=Org.objects.filter(name="New Org", parent=None),
        )

        # create child org
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"type": "child", "name": "Child Org", "timezone": "Africa/Nairobi"},
            new_obj_query=Org.objects.filter(name="Child Org", parent=self.org),
        )

    def test_create_child_spa(self):
        create_url = reverse("orgs.org_create")

        self.login(self.admin)

        self.org.features = [Org.FEATURE_CHILD_ORGS]
        self.org.save(update_fields=("features",))

        response = self.client.post(create_url, {"name": "Child Org", "timezone": "Africa/Nairobi"}, HTTP_X_TEMBA_SPA=1)

        self.assertRedirect(response, reverse("orgs.org_list"))

    def test_list(self):
        list_url = reverse("orgs.org_list")

        # nobody can access if child orgs feature not enabled
        response = self.requestView(list_url, self.admin)
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        # enable child orgs and create some child orgs
        self.org.features = [Org.FEATURE_CHILD_ORGS]
        self.org.save(update_fields=("features",))
        child1 = self.org.create_new(self.admin, "Child Org 1", self.org.timezone, as_child=True)
        child2 = self.org.create_new(self.admin, "Child Org 2", self.org.timezone, as_child=True)

        response = self.assertListFetch(
            list_url, [self.admin], context_objects=[self.org, child1, child2], choose_org=self.org
        )
        self.assertContains(response, "Child Org 1")
        self.assertContains(response, "Child Org 2")

        # can search by name
        self.assertListFetch(
            list_url + "?search=child", [self.admin], context_objects=[child1, child2], choose_org=self.org
        )

    def test_update(self):
        # enable child orgs and create some child orgs
        self.org.features = [Org.FEATURE_CHILD_ORGS]
        self.org.save(update_fields=("features",))
        child1 = self.org.create_new(self.admin, "Child Org 1", self.org.timezone, as_child=True)

        update_url = reverse("orgs.org_update", args=[child1.id])

        self.assertRequestDisallowed(update_url, [None, self.user, self.editor, self.agent, self.admin2])
        self.assertUpdateFetch(
            update_url, [self.admin], form_fields=["name", "timezone", "date_format", "language"], choose_org=self.org
        )

        response = self.assertUpdateSubmit(
            update_url,
            self.admin,
            {"name": "New Child Name", "timezone": "Africa/Nairobi", "date_format": "Y", "language": "es"},
        )

        child1.refresh_from_db()
        self.assertEqual("New Child Name", child1.name)
        self.assertEqual("/org/", response.url)

        # if org doesn't exist, 404
        response = self.requestView(reverse("orgs.org_update", args=[3464374]), self.admin, choose_org=self.org)
        self.assertEqual(404, response.status_code)

    def test_delete(self):
        self.org.features = [Org.FEATURE_CHILD_ORGS]
        self.org.save(update_fields=("features",))

        child = self.org.create_new(self.admin, "Child Workspace", self.org.timezone, as_child=True)
        delete_url = reverse("orgs.org_delete", args=[child.id])

        self.assertRequestDisallowed(delete_url, [None, self.user, self.editor, self.agent, self.admin2])
        self.assertDeleteFetch(delete_url, [self.admin], choose_org=self.org)

        # schedule for deletion
        response = self.client.get(delete_url)
        self.assertContains(response, "You are about to delete the workspace <b>Child Workspace</b>")

        # go through with it, redirects to workspaces list page
        response = self.client.post(delete_url)
        self.assertEqual(reverse("orgs.org_list"), response["X-Temba-Success"])

        child.refresh_from_db()
        self.assertFalse(child.is_active)

    def test_start(self):
        # the start view routes users based on their role
        start_url = reverse("orgs.org_start")

        # not authenticated, you should get a login redirect
        self.assertLoginRedirect(self.client.get(start_url))

        # now for all our roles
        self.assertRedirect(self.requestView(start_url, self.admin), "/msg/")
        self.assertRedirect(self.requestView(start_url, self.editor), "/msg/")
        self.assertRedirect(self.requestView(start_url, self.user), "/msg/")
        self.assertRedirect(self.requestView(start_url, self.agent), "/ticket/")

        # now try as customer support
        self.assertRedirect(self.requestView(start_url, self.customer_support), "/staff/org/")

        # if org isn't set, we redirect instead to choose view
        self.client.logout()
        self.org2.add_user(self.admin, OrgRole.ADMINISTRATOR)
        self.login(self.admin)
        self.assertRedirect(self.client.get(start_url), "/org/choose/")

    def test_choose(self):
        choose_url = reverse("orgs.org_choose")

        # create an inactive org which should never appear as an option
        org3 = Org.objects.create(
            name="Deactivated", timezone=tzone.utc, created_by=self.user, modified_by=self.user, is_active=False
        )
        org3.add_user(self.editor, OrgRole.EDITOR)

        # and another org that none of our users belong to
        org4 = Org.objects.create(name="Other", timezone=tzone.utc, created_by=self.user, modified_by=self.user)

        self.assertLoginRedirect(self.client.get(choose_url))

        # users with a single org are always redirected to the start page automatically
        self.assertRedirect(self.requestView(choose_url, self.admin), "/org/start/")
        self.assertRedirect(self.requestView(choose_url, self.editor), "/org/start/")
        self.assertRedirect(self.requestView(choose_url, self.user), "/org/start/")
        self.assertRedirect(self.requestView(choose_url, self.agent), "/org/start/")

        # users with no org are redirected back to the login page
        response = self.requestView(choose_url, self.non_org_user)
        self.assertLoginRedirect(response)
        response = self.client.get("/users/login/")
        self.assertContains(response, "No workspaces for this account, please contact your administrator.")

        # unless they are staff
        self.assertRedirect(self.requestView(choose_url, self.customer_support), "/staff/org/")

        # turn editor into a multi-org user
        self.org2.add_user(self.editor, OrgRole.EDITOR)

        # now we see a page to choose one of the two orgs
        response = self.requestView(choose_url, self.editor)
        self.assertEqual(["organization", "loc"], list(response.context["form"].fields.keys()))
        self.assertEqual({self.org, self.org2}, set(response.context["form"].fields["organization"].queryset))
        self.assertEqual({self.org, self.org2}, set(response.context["orgs"]))

        # try to submit for an org we don't belong to
        response = self.client.post(choose_url, {"organization": org4.id})
        self.assertFormError(
            response.context["form"],
            "organization",
            "Select a valid choice. That choice is not one of the available choices.",
        )

        # user clicks org 2...
        response = self.client.post(choose_url, {"organization": self.org2.id})
        self.assertRedirect(response, "/org/start/")

    def test_edit(self):
        edit_url = reverse("orgs.org_edit")

        self.assertLoginRedirect(self.client.get(edit_url))

        self.login(self.admin)

        response = self.client.get(edit_url)
        self.assertEqual(
            ["name", "timezone", "date_format", "language", "loc"], list(response.context["form"].fields.keys())
        )

        # language is only shown if there are multiple options
        with override_settings(LANGUAGES=(("en-us", "English"),)):
            response = self.client.get(edit_url)
            self.assertEqual(["name", "timezone", "date_format", "loc"], list(response.context["form"].fields.keys()))

        # try submitting with errors
        response = self.client.post(
            reverse("orgs.org_edit"),
            {"name": "", "timezone": "Bad/Timezone", "date_format": "X", "language": "klingon"},
        )
        self.assertFormError(response.context["form"], "name", "This field is required.")
        self.assertFormError(
            response.context["form"],
            "timezone",
            "Select a valid choice. Bad/Timezone is not one of the available choices.",
        )
        self.assertFormError(
            response.context["form"], "date_format", "Select a valid choice. X is not one of the available choices."
        )
        self.assertFormError(
            response.context["form"], "language", "Select a valid choice. klingon is not one of the available choices."
        )

        response = self.client.post(
            reverse("orgs.org_edit"),
            {"name": "New Name", "timezone": "Africa/Nairobi", "date_format": "Y", "language": "es"},
        )
        self.assertEqual(200, response.status_code)

        self.org.refresh_from_db()
        self.assertEqual("New Name", self.org.name)
        self.assertEqual("Africa/Nairobi", str(self.org.timezone))
        self.assertEqual("Y", self.org.date_format)
        self.assertEqual("es", self.org.language)

    def test_urn_schemes(self):
        # remove existing channels
        Channel.objects.all().update(is_active=False, org=None)

        self.assertEqual(set(), self.org.get_schemes(Channel.ROLE_SEND))
        self.assertEqual(set(), self.org.get_schemes(Channel.ROLE_RECEIVE))

        # add a receive only tel channel
        self.create_channel("T", "Twilio", "0785551212", country="RW", role="R")

        self.org = Org.objects.get(id=self.org.id)
        self.assertEqual(set(), self.org.get_schemes(Channel.ROLE_SEND))
        self.assertEqual({URN.TEL_SCHEME}, self.org.get_schemes(Channel.ROLE_RECEIVE))
        self.assertEqual({URN.TEL_SCHEME}, self.org.get_schemes(Channel.ROLE_RECEIVE))  # from cache

        # add a send/receive tel channel
        self.create_channel("T", "Twilio", "0785553434", country="RW", role="SR")

        self.org = Org.objects.get(pk=self.org.id)
        self.assertEqual({URN.TEL_SCHEME}, self.org.get_schemes(Channel.ROLE_SEND))
        self.assertEqual({URN.TEL_SCHEME}, self.org.get_schemes(Channel.ROLE_RECEIVE))

    def test_languages(self):
        settings_url = reverse("orgs.org_workspace")
        langs_url = reverse("orgs.org_languages")

        self.org.set_flow_languages(self.admin, ["eng"])

        response = self.requestView(settings_url, self.admin)
        self.assertEqual("English", response.context["primary_lang"])
        self.assertEqual([], response.context["other_langs"])

        self.assertRequestDisallowed(langs_url, [None, self.user, self.editor, self.agent])
        self.assertUpdateFetch(langs_url, [self.admin], form_fields=["primary_lang", "other_langs", "input_collation"])

        # initial should do a match on code only
        response = self.client.get(f"{langs_url}?initial=fra", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual([{"name": "French", "value": "fra"}], response.json()["results"])

        # try to submit as is (empty)
        self.assertUpdateSubmit(
            langs_url,
            self.admin,
            {},
            object_unchanged=self.org,
            form_errors={"primary_lang": "This field is required.", "input_collation": "This field is required."},
        )

        # give the org a primary language
        self.assertUpdateSubmit(
            langs_url,
            self.admin,
            {"primary_lang": '{"name":"French", "value":"fra"}', "input_collation": "confusables"},
            success_status=200,
        )

        self.org.refresh_from_db()
        self.assertEqual(["fra"], self.org.flow_languages)
        self.assertEqual("confusables", self.org.input_collation)

        # summary now includes this
        response = self.requestView(settings_url, self.admin)
        self.assertContains(response, "The default flow language is <b>French</b>.")
        self.assertNotContains(response, "Translations are provided in")

        # and now give it additional languages
        self.assertUpdateSubmit(
            langs_url,
            self.admin,
            {
                "primary_lang": '{"name":"French", "value":"fra"}',
                "other_langs": ['{"name":"Haitian", "value":"hat"}', '{"name":"Hausa", "value":"hau"}'],
                "input_collation": "confusables",
            },
            success_status=200,
        )

        self.org.refresh_from_db()
        self.assertEqual(["fra", "hat", "hau"], self.org.flow_languages)

        response = self.requestView(settings_url, self.admin)
        self.assertContains(response, "The default flow language is <b>French</b>.")
        self.assertContains(response, "Translations are provided in")
        self.assertContains(response, "<b>Hausa</b>")

        # searching languages should only return languages with 2-letter codes
        response = self.client.get("%s?search=Fr" % langs_url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(
            [
                {"value": "afr", "name": "Afrikaans"},
                {"value": "fra", "name": "French"},
                {"value": "fry", "name": "Western Frisian"},
            ],
            response.json()["results"],
        )

        # unless they're explicitly included in settings
        with override_settings(NON_ISO6391_LANGUAGES={"frc"}):
            languages.reload()
            response = self.client.get("%s?search=Fr" % langs_url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
            self.assertEqual(
                [
                    {"value": "afr", "name": "Afrikaans"},
                    {"value": "frc", "name": "Cajun French"},
                    {"value": "fra", "name": "French"},
                    {"value": "fry", "name": "Western Frisian"},
                ],
                response.json()["results"],
            )

        languages.reload()
