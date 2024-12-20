from temba.orgs.models import BackupToken
from temba.tests import TembaTest


class BackupTokenTest(TembaTest):
    def test_model(self):
        admin_tokens = BackupToken.generate_for_user(self.admin)
        BackupToken.generate_for_user(self.editor)

        self.assertEqual(10, len(admin_tokens))
        self.assertEqual(10, self.admin.backup_tokens.count())
        self.assertEqual(10, self.editor.backup_tokens.count())
        self.assertEqual(str(admin_tokens[0].token), str(admin_tokens[0]))

        # regenerate tokens for admin user
        new_admin_tokens = BackupToken.generate_for_user(self.admin)
        self.assertEqual(10, len(new_admin_tokens))
        self.assertNotEqual([t.token for t in admin_tokens], [t.token for t in new_admin_tokens])
        self.assertEqual(10, self.admin.backup_tokens.count())
