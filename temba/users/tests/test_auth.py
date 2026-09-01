from urllib.parse import urlencode

from allauth.account.models import EmailAddress

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from django.utils.functional import lazystr

from temba.orgs.models import Invitation, OrgRole
from temba.tests.base import TembaTest
from temba.users.models import User


class UserAuthTest(TembaTest):
    # Auth is handled by allauth, only test things we override in any way
    def test_no_workspace_alert(self):
        # users with a workspace don't see the invitation-needed alert on account pages
        self.login(self.admin)
        response = self.client.get(reverse("account_change_password"))
        self.assertNotContains(response, "need an invitation to continue")

        # but users without one do
        user = User.create(
            email="noworkspace@temba.io", first_name="Nelly", last_name="Noworkspace", password="Qwerty123"
        )
        self.login(user)
        response = self.client.get(reverse("account_change_password"))
        self.assertContains(response, "need an invitation to continue")

        # unless the brand offers self-serve signup
        with override_settings(BRAND={**settings.BRAND, "signup_url": "/org/signup/"}):
            response = self.client.get(reverse("account_change_password"))
            self.assertNotContains(response, "need an invitation to continue")

    def test_login_with_invalid_invite(self):
        response = self.client.get(f"{reverse('account_login')}?invite=invalid")
        self.assertContains(response, "Sorry, your invitation is no longer valid. Please request a new invite.")

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
            f"{reverse('account_reauthenticate')}?{urlencode({'next': mfa_url})}",
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

    @override_settings(
        SSO_LOGIN_WARNING_DOMAINS={"SSO-Corp.com": lazystr("Use <b>Sign In with SSO Corp</b> next time.")}
    )
    def test_sso_login_warning(self):
        login_url = reverse("account_login")

        def create_verified_user(email):
            user = self.create_user(email)
            EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
            self.org.add_user(user, OrgRole.EDITOR)
            return user

        # logging in with a password from a non-matching domain doesn't warn
        response = self.client.post(
            login_url, {"login": self.admin.email, "password": self.default_password}, follow=True
        )
        self.assertNotContains(response, "sso-login-warning")

        self.client.logout()

        # but a user whose email domain should be using SSO gets the warning configured for that domain, escaped
        user = create_verified_user("uma@sso-corp.com")

        response = self.client.post(login_url, {"login": user.email, "password": self.default_password}, follow=True)
        self.assertContains(response, "sso-login-warning")
        self.assertContains(response, 'header="Use Single Sign-On"')
        self.assertContains(response, "Use &lt;b&gt;Sign In with SSO Corp&lt;/b&gt; next time.")

        # only on the first page load after login
        response = self.client.get(response.request["PATH_INFO"])
        self.assertNotContains(response, "sso-login-warning")

        # a flagged domain that is no longer configured doesn't warn
        session = self.client.session
        session["sso_login_warning"] = "old-corp.com"
        session.save()

        response = self.client.get(response.request["PATH_INFO"])
        self.assertNotContains(response, "sso-login-warning")

    def test_signup(self):
        signup_url = reverse("account_signup")

        # signup without an invite is closed
        response = self.client.get(signup_url)
        self.assertContains(response, "Sign Up Closed")

        # we also need to ensure they can't post
        response = self.client.post(
            signup_url,
            {
                "first_name": "Bobby",
                "last_name": "Burgers",
                "password1": "arstqwfp",
                "email": "bobbyburgers@burgers.com",
            },
        )
        self.assertContains(response, "Sign Up Closed")

        # but we still need to be able to accept an invite
        invitation = Invitation.create(self.org, self.admin, "bob@textit.com", OrgRole.ADMINISTRATOR)
        invite_signup = f"{signup_url}?invite={invitation.secret}"

        response = self.client.get(invite_signup)
        self.assertNotContains(response, "Sign Up Closed")

        # and we should be able to post - to the bare URL as browsers do, relying on the invite secret stored in the
        # session by the GET above.. and we handle tampering with the invite
        response = self.client.post(
            signup_url,
            {
                "first_name": "Bobby",
                "last_name": "Burgers",
                "email": "bobbyburgers@burgers.com",
                "password1": "arstqwfp",
            },
            follow=True,
        )

        # should get signed up, logged in and redirected to inbox
        self.assertNotContains(response, "Sign Up Closed")
        self.assertContains(response, "temba-msg-list")

        # make sure we didn't honor the tampered email
        self.assertFalse(User.objects.filter(email="bobbyburgers@burgers.com").exists())

        # we should now have a new user with the invitation email
        user = User.objects.filter(email="bob@textit.com").first()
        self.assertIsNotNone(user)

        email = user.emailaddress_set.all().first()
        self.assertTrue(email.verified)
