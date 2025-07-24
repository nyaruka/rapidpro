from temba.contacts.models import ContactField, ContactGroup
from temba.tests import MigrationTest


class ClearFieldDepsForDeletedGroups(MigrationTest):
    app = "contacts"
    migrate_from = "0209_alter_contactgroup_status"
    migrate_to = "0210_clear_deps_for_deleted_groups"

    def setUpBeforeMigration(self, apps):
        self.age = self.create_field("age", "Age", ContactField.TYPE_NUMBER)

        # deleted manual group, no fields
        self.group1 = ContactGroup.objects.create(
            org=self.org,
            uuid="f3f1b95f-52c5-4144-9d6a-08fd830d0a52",
            name="G1",
            group_type=ContactGroup.TYPE_MANUAL,
            query="age < 18",
            created_by=self.admin,
            modified_by=self.admin,
            is_active=False,
        )

        # deleted query group, no fields
        self.group2 = ContactGroup.objects.create(
            org=self.org,
            uuid="d288b300-b61f-447d-9c61-8b1b213e39c2",
            name="G2",
            group_type=ContactGroup.TYPE_SMART,
            query='name = ""',
            created_by=self.admin,
            modified_by=self.admin,
            is_active=False,
        )

        # deleted query group, field dependency
        self.group3 = ContactGroup.objects.create(
            org=self.org,
            uuid="0c844663-7f69-4781-b3b1-afff5e86a594",
            name="G3",
            group_type=ContactGroup.TYPE_SMART,
            query="age = 44",
            created_by=self.admin,
            modified_by=self.admin,
            is_active=False,
        )
        self.group3.query_fields.add(self.age)

        # still active query group, field dependency
        self.group4 = ContactGroup.objects.create(
            org=self.org,
            uuid="2c458837-5c99-452c-94c6-8f4a5d9236d1",
            name="G4",
            group_type=ContactGroup.TYPE_SMART,
            query="age = 44",
            created_by=self.admin,
            modified_by=self.admin,
            is_active=True,
        )
        self.group4.query_fields.add(self.age)

    def test_migration(self):
        self.assertEqual(set(), set(self.group1.query_fields.all()))
        self.assertEqual(set(), set(self.group2.query_fields.all()))
        self.assertEqual(set(), set(self.group3.query_fields.all()))  # cleared
        self.assertEqual({self.age}, set(self.group4.query_fields.all()))
