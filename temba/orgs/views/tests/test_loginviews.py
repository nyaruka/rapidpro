from datetime import timedelta
from unittest.mock import patch

from smartmin.users.models import FailedLogin

from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from temba.tests import TembaTest


class LoginViewsTest(TembaTest):
    def test_login(self):
        login_url = reverse("orgs.login")
        verify_url = reverse("orgs.two_factor_verify")
        backup_url = reverse("orgs.two_factor_backup")

        self.assertIsNone(self.admin.settings.last_auth_on)

        # try to access a non-public page
        response = self.client.get(reverse("msgs.msg_inbox"))
        self.assertLoginRedirect(response)
        self.assertTrue(response.url.endswith("?next=/msg/"))

        # view login page
        response = self.client.get(login_url)
        self.assertEqual(200, response.status_code)
        self.assertEqual(list(response.context["form"].fields.keys()), ["username", "password"])

        # submit empty username and password
        response = self.client.post(login_url, {"username": "", "password": ""})
        self.assertFormError(response.context["form"], "username", "This field is required.")
        self.assertFormError(response.context["form"], "password", "This field is required.")

        # submit incorrect username and password
        response = self.client.post(login_url, {"username": "jim", "password": "pass123"})
        self.assertEqual(200, response.status_code)
        self.assertFormError(
            response.context["form"],
            None,
            "Please enter a correct username and password. Note that both fields may be case-sensitive.",
        )

        # submit incorrect password by case sensitivity
        response = self.client.post(login_url, {"username": "admin@textit.com", "password": "QWERTY123"})
        self.assertEqual(200, response.status_code)
        self.assertFormError(
            response.context["form"],
            None,
            "Please enter a correct username and password. Note that both fields may be case-sensitive.",
        )

        # submit correct username and password
        response = self.client.post(login_url, {"username": "admin@textit.com", "password": "Qwerty123"})
        self.assertRedirect(response, reverse("orgs.org_choose"))

        self.admin.settings.refresh_from_db()
        self.assertIsNotNone(self.admin.settings.last_auth_on)

        # logout and enable 2FA
        self.client.logout()
        self.admin.enable_2fa()

        # can't access two-factor verify page yet
        response = self.client.get(verify_url)
        self.assertLoginRedirect(response)

        # login via login page again
        response = self.client.post(
            login_url + "?next=/msg/", {"username": "admin@textit.com", "password": "Qwerty123"}
        )
        self.assertRedirect(response, verify_url)
        self.assertTrue(response.url.endswith("?next=/msg/"))

        # view two-factor verify page
        response = self.client.get(verify_url)
        self.assertEqual(200, response.status_code)
        self.assertEqual(["otp"], list(response.context["form"].fields.keys()))
        self.assertContains(response, backup_url)

        # enter invalid OTP
        response = self.client.post(verify_url, {"otp": "nope"})
        self.assertFormError(response.context["form"], "otp", "Incorrect OTP. Please try again.")

        # enter valid OTP
        with patch("pyotp.TOTP.verify", return_value=True):
            response = self.client.post(verify_url, {"otp": "123456"})
        self.assertRedirect(response, reverse("orgs.org_choose"))

        self.client.logout()

        # login via login page again
        response = self.client.post(login_url, {"username": "admin@textit.com", "password": "Qwerty123"})
        self.assertRedirect(response, verify_url)

        # but this time we've lost our phone so go to the page for backup tokens
        response = self.client.get(backup_url)
        self.assertEqual(200, response.status_code)
        self.assertEqual(["token"], list(response.context["form"].fields.keys()))

        # enter invalid backup token
        response = self.client.post(backup_url, {"token": "nope"})
        self.assertFormError(response.context["form"], "token", "Invalid backup token. Please try again.")

        # enter valid backup token
        response = self.client.post(backup_url, {"token": self.admin.backup_tokens.first()})
        self.assertRedirect(response, reverse("orgs.org_choose"))

        self.assertEqual(9, len(self.admin.backup_tokens.filter(is_used=False)))

    @override_settings(USER_LOCKOUT_TIMEOUT=1, USER_FAILED_LOGIN_LIMIT=3)
    def test_login_lockouts(self):
        login_url = reverse("orgs.login")
        verify_url = reverse("orgs.two_factor_verify")
        backup_url = reverse("orgs.two_factor_backup")
        failed_url = reverse("orgs.user_failed")

        # submit incorrect username and password 3 times
        self.client.post(login_url, {"username": "admin@textit.com", "password": "pass123"})
        self.client.post(login_url, {"username": "admin@textit.com", "password": "pass123"})
        response = self.client.post(login_url, {"username": "admin@textit.com", "password": "pass123"})

        self.assertRedirect(response, failed_url)
        self.assertRedirect(self.client.get(reverse("msgs.msg_inbox")), login_url)

        # simulate failed logins timing out by making them older
        FailedLogin.objects.all().update(failed_on=timezone.now() - timedelta(minutes=3))

        # now we're allowed to make failed logins again
        response = self.client.post(login_url, {"username": "admin@textit.com", "password": "pass123"})
        self.assertFormError(
            response.context["form"],
            None,
            "Please enter a correct username and password. Note that both fields may be case-sensitive.",
        )

        # and successful logins
        response = self.client.post(login_url, {"username": "admin@textit.com", "password": "Qwerty123"})
        self.assertRedirect(response, reverse("orgs.org_choose"))

        # try again with 2FA enabled
        self.client.logout()
        self.admin.enable_2fa()

        # submit incorrect username and password 3 times
        self.client.post(login_url, {"username": "admin@textit.com", "password": "pass123"})
        self.client.post(login_url, {"username": "admin@textit.com", "password": "pass123"})
        response = self.client.post(login_url, {"username": "admin@textit.com", "password": "pass123"})

        self.assertRedirect(response, failed_url)
        self.assertRedirect(self.client.get(reverse("msgs.msg_inbox")), login_url)

        # login correctly
        FailedLogin.objects.all().delete()
        response = self.client.post(login_url, {"username": "admin@textit.com", "password": "Qwerty123"})
        self.assertRedirect(response, verify_url)

        # now enter a backup token 3 times incorrectly
        self.client.post(backup_url, {"token": "nope"})
        self.client.post(backup_url, {"token": "nope"})
        response = self.client.post(backup_url, {"token": "nope"})

        self.assertRedirect(response, failed_url)
        self.assertRedirect(self.client.get(verify_url), login_url)
        self.assertRedirect(self.client.get(backup_url), login_url)
        self.assertRedirect(self.client.get(reverse("msgs.msg_inbox")), login_url)

        # simulate failed logins timing out by making them older
        FailedLogin.objects.all().update(failed_on=timezone.now() - timedelta(minutes=3))

        # we can't enter backup tokens again without going thru regular login first
        response = self.client.post(backup_url, {"token": "nope"})
        self.assertRedirect(response, login_url)

        response = self.client.post(login_url, {"username": "admin@textit.com", "password": "Qwerty123"})
        self.assertRedirect(response, verify_url)

        response = self.client.post(backup_url, {"token": self.admin.backup_tokens.first()})
        self.assertRedirect(response, reverse("orgs.org_choose"))

    def test_logout(self):
        logout_url = reverse("orgs.logout")

        self.assertEqual(405, self.client.get(logout_url).status_code)

        self.login(self.admin)

        response = self.client.post(logout_url)
        self.assertLoginRedirect(response)

    @override_settings(USER_LOCKOUT_TIMEOUT=1, USER_FAILED_LOGIN_LIMIT=3)
    def test_confirm_access(self):
        confirm_url = reverse("orgs.confirm_access") + "?next=/msg/"
        failed_url = reverse("orgs.user_failed")

        # try to access before logging in
        response = self.client.get(confirm_url)
        self.assertLoginRedirect(response)

        self.login(self.admin)

        response = self.client.get(confirm_url)
        self.assertEqual(["password"], list(response.context["form"].fields.keys()))

        # try to submit with incorrect password
        response = self.client.post(confirm_url, {"password": "nope"})
        self.assertFormError(response.context["form"], "password", "Password incorrect.")

        # 2 more times..
        self.client.post(confirm_url, {"password": "nope"})
        response = self.client.post(confirm_url, {"password": "nope"})
        self.assertRedirect(response, failed_url)

        # and we are logged out
        self.assertLoginRedirect(self.client.get(confirm_url))
        self.assertLoginRedirect(self.client.get(reverse("msgs.msg_inbox")))

        FailedLogin.objects.all().delete()

        # can once again submit incorrect passwords
        self.login(self.admin)
        response = self.client.post(confirm_url, {"password": "nope"})
        self.assertFormError(response.context["form"], "password", "Password incorrect.")

        # and also correct ones
        response = self.client.post(confirm_url, {"password": "Qwerty123"})
        self.assertRedirect(response, "/msg/")

        # check we don't require 2FA even if enabled
        self.admin.enable_2fa()

        response = self.client.post(confirm_url, {"password": "Qwerty123"})
        self.assertRedirect(response, "/msg/")

    def test_two_factor_views(self):
        enable_url = reverse("orgs.user_two_factor_enable")
        tokens_url = reverse("orgs.user_two_factor_tokens")
        disable_url = reverse("orgs.user_two_factor_disable")

        self.login(self.admin, update_last_auth_on=True)

        # view form to enable 2FA
        response = self.client.get(enable_url)
        self.assertEqual(["otp", "confirm_password", "loc"], list(response.context["form"].fields.keys()))

        # try to submit with no OTP or password
        response = self.client.post(enable_url, {})
        self.assertFormError(response.context["form"], "otp", "This field is required.")
        self.assertFormError(response.context["form"], "confirm_password", "This field is required.")

        # try to submit with invalid OTP and password
        response = self.client.post(enable_url, {"otp": "nope", "confirm_password": "wrong"})
        self.assertFormError(response.context["form"], "otp", "OTP incorrect. Please try again.")
        self.assertFormError(response.context["form"], "confirm_password", "Password incorrect.")

        # submit with valid OTP and password
        with patch("pyotp.TOTP.verify", return_value=True):
            response = self.client.post(enable_url, {"otp": "123456", "confirm_password": "Qwerty123"})
        self.assertRedirect(response, tokens_url)

        self.admin.settings.refresh_from_db()
        self.assertTrue(self.admin.settings.two_factor_enabled)

        # view backup tokens page
        response = self.client.get(tokens_url)
        self.assertContains(response, "Regenerate Tokens")

        tokens = [t.token for t in response.context["backup_tokens"]]

        # posting to that page regenerates tokens
        response = self.client.post(tokens_url)
        self.assertToast(response, "info", "Two-factor authentication backup tokens changed.")
        self.assertNotEqual(tokens, [t.token for t in response.context["backup_tokens"]])

        # view form to disable 2FA
        response = self.client.get(disable_url)
        self.assertEqual(["confirm_password", "loc"], list(response.context["form"].fields.keys()))

        # try to submit with no password
        response = self.client.post(disable_url, {})
        self.assertFormError(response.context["form"], "confirm_password", "This field is required.")

        # try to submit with invalid password
        response = self.client.post(disable_url, {"confirm_password": "wrong"})
        self.assertFormError(response.context["form"], "confirm_password", "Password incorrect.")

        # submit with valid password
        response = self.client.post(disable_url, {"confirm_password": "Qwerty123"})
        self.assertRedirect(response, reverse("orgs.user_account"))

        self.admin.settings.refresh_from_db()
        self.assertFalse(self.admin.settings.two_factor_enabled)

        # trying to view the tokens page now takes us to the enable form
        response = self.client.get(tokens_url)
        self.assertRedirect(response, enable_url)

    def test_two_factor_time_limit(self):
        login_url = reverse("orgs.login")
        verify_url = reverse("orgs.two_factor_verify")
        backup_url = reverse("orgs.two_factor_backup")

        self.admin.enable_2fa()

        # simulate a login for a 2FA user 10 minutes ago
        with patch("django.utils.timezone.now", return_value=timezone.now() - timedelta(minutes=10)):
            response = self.client.post(login_url, {"username": "admin@textit.com", "password": "Qwerty123"})
            self.assertRedirect(response, verify_url)

            response = self.client.get(verify_url)
            self.assertEqual(200, response.status_code)

        # if they access the verify or backup page now, they are redirected back to the login page
        response = self.client.get(verify_url)
        self.assertRedirect(response, login_url)

        response = self.client.get(backup_url)
        self.assertRedirect(response, login_url)

    def test_two_factor_confirm_access(self):
        tokens_url = reverse("orgs.user_two_factor_tokens")

        self.admin.enable_2fa()
        self.login(self.admin, update_last_auth_on=False)

        # but navigating to tokens page redirects to confirm auth
        response = self.client.get(tokens_url)
        self.assertEqual(302, response.status_code)
        self.assertTrue(response.url.endswith("/users/confirm-access/?next=/user/two_factor_tokens/"))

        confirm_url = response.url

        # view confirm access page
        response = self.client.get(confirm_url)
        self.assertEqual(["password"], list(response.context["form"].fields.keys()))

        # try to submit with incorrect password
        response = self.client.post(confirm_url, {"password": "nope"})
        self.assertFormError(response.context["form"], "password", "Password incorrect.")

        # submit with real password
        response = self.client.post(confirm_url, {"password": "Qwerty123"})
        self.assertRedirect(response, tokens_url)

        response = self.client.get(tokens_url)
        self.assertEqual(200, response.status_code)
