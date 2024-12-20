from unittest.mock import patch

from temba.api.models import APIToken
from temba.orgs.models import OrgRole, User, UserSettings
from temba.tests import TembaTest, mock_mailroom


class UserTest(TembaTest):
    def test_model(self):
        user = User.create("jim@rapidpro.io", "Jim", "McFlow", password="super")

        self.assertTrue(UserSettings.objects.filter(user=user).exists())  # created by signal

        with self.assertNumQueries(0):
            self.assertIsNone(user.settings.last_auth_on)

        # reload the user instance - now accessing settings should lazily trigger a query
        user = User.objects.get(id=user.id)
        with self.assertNumQueries(1):
            self.assertIsNone(user.settings.last_auth_on)
        with self.assertNumQueries(0):
            self.assertIsNone(user.settings.last_auth_on)

        # unless we prefetch
        user = User.objects.select_related("settings").get(id=user.id)
        with self.assertNumQueries(0):
            self.assertIsNone(user.settings.last_auth_on)

        self.org.add_user(user, OrgRole.EDITOR)
        self.org2.add_user(user, OrgRole.AGENT)

        self.assertEqual("Jim McFlow", user.name)
        self.assertFalse(user.is_alpha)
        self.assertFalse(user.is_beta)
        self.assertEqual({"email": "jim@rapidpro.io", "name": "Jim McFlow"}, user.as_engine_ref())
        self.assertEqual([self.org, self.org2], list(user.get_orgs().order_by("id")))

        user.last_name = ""
        user.save(update_fields=("last_name",))

        self.assertEqual("Jim", user.name)
        self.assertEqual({"email": "jim@rapidpro.io", "name": "Jim"}, user.as_engine_ref())

    def test_has_org_perm(self):
        granter = self.create_user("jim@rapidpro.io", group_names=("Granters",))

        tests = (
            (
                self.org,
                "contacts.contact_list",
                {self.agent: False, self.user: True, self.admin: True, self.admin2: False},
            ),
            (
                self.org2,
                "contacts.contact_list",
                {self.agent: False, self.user: False, self.admin: False, self.admin2: True},
            ),
            (
                self.org2,
                "contacts.contact_read",
                {self.agent: False, self.user: False, self.admin: False, self.admin2: True},
            ),
            (
                self.org,
                "orgs.org_edit",
                {self.agent: False, self.user: False, self.admin: True, self.admin2: False},
            ),
            (
                self.org2,
                "orgs.org_edit",
                {self.agent: False, self.user: False, self.admin: False, self.admin2: True},
            ),
            (
                self.org,
                "orgs.org_grant",
                {self.agent: False, self.user: False, self.admin: False, self.admin2: False, granter: True},
            ),
            (
                self.org,
                "xxx.yyy_zzz",
                {self.agent: False, self.user: False, self.admin: False, self.admin2: False},
            ),
        )
        for org, perm, checks in tests:
            for user, has_perm in checks.items():
                self.assertEqual(
                    has_perm,
                    user.has_org_perm(org, perm),
                    f"expected {user} to{'' if has_perm else ' not'} have perm {perm} in org {org.name}",
                )

    def test_two_factor(self):
        self.assertFalse(self.admin.settings.two_factor_enabled)

        self.admin.enable_2fa()

        self.assertTrue(self.admin.settings.two_factor_enabled)
        self.assertEqual(10, len(self.admin.backup_tokens.filter(is_used=False)))

        # try to verify with.. nothing
        self.assertFalse(self.admin.verify_2fa())

        # try to verify with an invalid OTP
        self.assertFalse(self.admin.verify_2fa(otp="nope"))

        # try to verify with a valid OTP
        with patch("pyotp.TOTP.verify", return_value=True):
            self.assertTrue(self.admin.verify_2fa(otp="123456"))

        # try to verify with an invalid backup token
        self.assertFalse(self.admin.verify_2fa(backup_token="nope"))

        # try to verify with a valid backup token
        token = self.admin.backup_tokens.first().token
        self.assertTrue(self.admin.verify_2fa(backup_token=token))

        self.assertEqual(9, len(self.admin.backup_tokens.filter(is_used=False)))

        # can't verify again with same backup token
        self.assertFalse(self.admin.verify_2fa(backup_token=token))

        self.admin.disable_2fa()

        self.assertFalse(self.admin.settings.two_factor_enabled)

    @mock_mailroom
    def test_release(self, mr_mocks):
        token = APIToken.create(self.org, self.admin)

        # admin doesn't "own" any orgs
        self.assertEqual(0, len(self.admin.get_owned_orgs()))

        # release all but our admin
        self.editor.release(self.customer_support)
        self.user.release(self.customer_support)
        self.agent.release(self.customer_support)

        # still a user left, our org remains active
        self.org.refresh_from_db()
        self.assertTrue(self.org.is_active)

        # now that we are the last user, we own it now
        self.assertEqual(1, len(self.admin.get_owned_orgs()))
        self.admin.release(self.customer_support)

        # and we take our org with us
        self.org.refresh_from_db()
        self.assertFalse(self.org.is_active)

        token.refresh_from_db()
        self.assertFalse(token.is_active)
