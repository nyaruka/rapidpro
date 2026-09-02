from django.contrib.auth.models import Group

from temba.tests import MigrationTest
from temba.users.models import User


class ResetDroppedLanguagesTest(MigrationTest):
    app = "users"
    migrate_from = "0021_user_settings"
    migrate_to = "0023_reset_dropped_languages"

    def setUpBeforeMigration(self, apps):
        # self.admin keeps a still supported language and should be untouched
        User.objects.filter(id=self.admin.id).update(language="pt-br")
        User.objects.filter(id=self.editor.id).update(language="ru")
        User.objects.filter(id=self.agent.id).update(language="mn")

    def test_migration(self):
        self.admin.refresh_from_db()
        self.editor.refresh_from_db()
        self.agent.refresh_from_db()

        self.assertEqual("pt-br", self.admin.language)
        self.assertEqual("en-us", self.editor.language)
        self.assertEqual("en-us", self.agent.language)


class RenameGrantersGroupTest(MigrationTest):
    app = "users"
    migrate_from = "0023_reset_dropped_languages"
    migrate_to = "0024_rename_granters_group"

    def setUpBeforeMigration(self, apps):
        Group.objects.filter(name="Global Administrators").update(name="Granters")
        self.editor.groups.add(Group.objects.get(name="Granters"))

    def test_migration(self):
        self.assertFalse(Group.objects.filter(name="Granters").exists())
        self.assertEqual(["Global Administrators"], list(self.editor.groups.values_list("name", flat=True)))
