from temba.tests import MigrationTest


class BackfillNameTest(MigrationTest):
    app = "users"
    migrate_from = "0010_user_name_alter_user_date_joined_and_more"
    migrate_to = "0011_backfill_name"

    def setUpBeforeMigration(self, apps):
        self.editor.name = ""
        self.editor.save(update_fields=("name",))

    def test_migration(self):
        self.editor.refresh_from_db()
        self.assertEqual(self.editor.name, "Ed McEdits")
