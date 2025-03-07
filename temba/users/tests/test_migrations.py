from temba.tests import MigrationTest


class MigrateMFATest(MigrationTest):
    app = "users"
    migrate_from = "0012_remove_user_username"
    migrate_to = "0013_migrate_mfa"

    def setUpBeforeMigration(self, apps):

        # enable 2fa using the old method
        self.admin.enable_2fa()
        self.assertTrue(self.admin.two_factor_enabled)

        # mark our email address as verified
        self.admin.email_status = "V"
        self.admin.save(update_fields=("email_status",))

    def test_migration(self):

        # we should now have the allauth equivalent of 2fa enabled
        [totp, recovery] = self.admin.authenticator_set.all()
        email = self.admin.emailaddress_set.all().first()

        # it should be verified and primary
        self.assertIsNotNone(email)
        self.assertTrue(email.verified)
        self.assertTrue(email.primary)

        # we should have a TOTP authenticator
        self.assertEqual(totp.type, "totp")
        self.assertEqual(totp.user, self.admin)
        self.assertEqual(totp.data["secret"], self.admin.two_factor_secret)

        # we should have a recovery codes authenticator
        self.assertEqual(recovery.type, "recovery_codes")
        self.assertEqual(recovery.user, self.admin)
        self.assertEqual(len(recovery.data["migrated_codes"]), 10)
        self.assertEqual(
            set(recovery.data["migrated_codes"]),
            set(self.admin.backup_tokens.values_list("token", flat=True)),
        )
