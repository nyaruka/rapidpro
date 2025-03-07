from urllib.parse import urlencode

from django.urls import reverse

from temba.tests.base import TembaTest


class UserAuthTest(TembaTest):

    # Auth is handled by allauth, only test things we override in any way
    def test_signup(self):
        signup_url = reverse("account_signup")
        success_url = reverse("orgs.org_choose")

        response = self.client.get(signup_url)
        self.assertEqual(200, response.status_code)

        # bad inputs
        response = self.client.post(signup_url, {"email": "invalid"})
        self.assertEqual(200, response.status_code)
        form = response.context.get("form")
        self.assertFormError(form, "email", "Enter a valid email address.")
        self.assertFormError(form, "first_name", "This field is required.")
        self.assertFormError(form, "last_name", "This field is required.")
        self.assertFormError(form, "workspace", "This field is required.")

        # test valid signup
        response = self.client.post(
            signup_url,
            {
                "first_name": "Bobby",
                "last_name": "Burgers",
                "workspace": "Bobby's Burgers",
                "password1": "arstqwfp",
                "email": "bobbyburgers@burgers.com",
                "timezone": "America/New_York",
            },
        )

        self.assertRedirect(response, success_url)

    def test_change_password(self):

        # make sure we get the correct help text on change password page
        self.login(self.admin)

        change_password_url = reverse("account_change_password")
        response = self.client.get(change_password_url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "At least 8 characters or more")

    def test_mfa(self):
        self.login(self.admin)
        mfa_url = reverse("mfa_activate_totp")

        # we should be forced to reauthenticate before we can get to mfa
        response = self.client.get(mfa_url)
        self.assertRedirect(response, reverse("account_reauthenticate"))

        # Reauthenticate and make sure we get the QR code
        response = self.client.post(
            f"{reverse("account_reauthenticate")}?{urlencode({'next': mfa_url})}",
            {"login": self.admin.email, "password": self.default_password},
            follow=True,
        )
        self.assertContains(response, "scan the QR code below")

    def test_add_email(self):
        # we override change email to ensure the new email is not already in use
        self.login(self.admin)
        add_email_url = reverse("account_email")

        # try to change our email address to one that is already in use
        response = self.client.post(add_email_url, {"email": self.admin2.email, "action_add": True})

        self.assertEqual(200, response.status_code)
        form = response.context.get("form")
        self.assertFormError(form, "email", "This email is already in use")

        # now try to change our email address to a new one
        response = self.client.post(add_email_url, {"email": "newemail@temba.io", "action_add": True})
        self.assertRedirect(response, reverse("account_email"))

        # we should see the new email now
        emails = self.admin.emailaddress_set.all()
        self.assertEqual(2, emails.count())
        self.assertTrue(emails.filter(email="newemail@temba.io").exists())
