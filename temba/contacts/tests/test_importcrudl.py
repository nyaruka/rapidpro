from unittest.mock import patch

from django.test.utils import override_settings
from django.urls import reverse

from temba.contacts.models import ContactField, ContactGroup, ContactImport
from temba.tests import CRUDLTestMixin, TembaTest, mock_mailroom


class ContactImportCRUDLTest(TembaTest, CRUDLTestMixin):
    @mock_mailroom
    def test_create_and_preview(self, mr_mocks):
        create_url = reverse("contacts.contactimport_create")

        self.assertRequestDisallowed(create_url, [None, self.agent])
        self.assertCreateFetch(create_url, [self.editor, self.admin], form_fields=["file"])

        # try posting with nothing
        response = self.client.post(create_url, {})
        self.assertFormError(response.context["form"], "file", "This field is required.")

        # try uploading an empty file
        response = self.client.post(create_url, {"file": self.upload("media/test_imports/empty.xlsx")})
        self.assertFormError(response.context["form"], "file", "Import file doesn't contain any records.")

        # try uploading a valid XLSX file
        response = self.client.post(create_url, {"file": self.upload("media/test_imports/simple.xlsx")})
        self.assertEqual(302, response.status_code)

        imp = ContactImport.objects.get()
        self.assertEqual(self.org, imp.org)
        self.assertEqual(3, imp.num_records)
        self.assertRegex(imp.file.name, rf"orgs/{self.org.id}/contact_imports/[\w-]{{36}}.xlsx$")
        self.assertEqual("simple.xlsx", imp.original_filename)
        self.assertIsNone(imp.started_on)
        self.assertIsNone(imp.group)

        preview_url = reverse("contacts.contactimport_preview", args=[imp.id])
        read_url = reverse("contacts.contactimport_read", args=[imp.id])

        # will have been redirected to the preview view for the new import
        self.assertEqual(preview_url, response.url)

        response = self.client.get(preview_url)
        self.assertContains(response, "URN:Tel")
        self.assertContains(response, "name")

        response = self.client.post(preview_url, {})
        self.assertEqual(302, response.status_code)
        self.assertEqual(read_url, response.url)

        imp.refresh_from_db()
        self.assertIsNotNone(imp.started_on)

        # can no longer access preview URL.. will be redirected to read
        response = self.client.get(preview_url)
        self.assertEqual(302, response.status_code)
        self.assertEqual(read_url, response.url)

    @mock_mailroom
    def test_creating_new_group(self, mr_mocks):
        self.login(self.admin)
        imp = self.create_contact_import("media/test_imports/simple.xlsx")
        preview_url = reverse("contacts.contactimport_preview", args=[imp.id])
        read_url = reverse("contacts.contactimport_read", args=[imp.id])

        # create some groups
        self.create_group("Testers", contacts=[])
        doctors = self.create_group("Doctors", contacts=[])

        # try creating new group but not providing a name
        response = self.client.post(preview_url, {"add_to_group": True, "group_mode": "N", "new_group_name": "  "})
        self.assertFormError(response.context["form"], "new_group_name", "Required.")

        # try creating new group but providing an invalid name
        response = self.client.post(preview_url, {"add_to_group": True, "group_mode": "N", "new_group_name": '"Foo"'})
        self.assertFormError(response.context["form"], "new_group_name", "Invalid group name.")

        # try creating new group but providing a name of an existing group
        response = self.client.post(preview_url, {"add_to_group": True, "group_mode": "N", "new_group_name": "testERs"})
        self.assertFormError(response.context["form"], "new_group_name", "Already exists.")

        # no option for creating new group when we've already reached our group limit
        with override_settings(ORG_LIMIT_DEFAULTS={"groups": 2, "fields": 1}):
            response = self.client.get(preview_url)
            self.assertEqual(response.context["form"].fields["group_mode"].choices, [("E", "existing group")])

        # finally create new group...
        response = self.client.post(preview_url, {"add_to_group": True, "group_mode": "N", "new_group_name": "Import"})
        self.assertRedirect(response, read_url)

        new_group = ContactGroup.objects.get(name="Import")
        imp.refresh_from_db()
        self.assertEqual(new_group, imp.group)

        # existing group should not check for workspace limit
        imp = self.create_contact_import("media/test_imports/simple.xlsx")
        preview_url = reverse("contacts.contactimport_preview", args=[imp.id])
        read_url = reverse("contacts.contactimport_read", args=[imp.id])
        with override_settings(ORG_LIMIT_DEFAULTS={"groups": 2, "fields": 1}):
            response = self.client.post(
                preview_url, {"add_to_group": True, "group_mode": "E", "existing_group": doctors.id}
            )
            self.assertRedirect(response, read_url)
            imp.refresh_from_db()
            self.assertEqual(doctors, imp.group)

    @mock_mailroom
    def test_using_existing_group(self, mr_mocks):
        self.login(self.admin)
        imp = self.create_contact_import("media/test_imports/simple.xlsx")
        preview_url = reverse("contacts.contactimport_preview", args=[imp.id])
        read_url = reverse("contacts.contactimport_read", args=[imp.id])

        # create some groups
        self.create_field("age", "Age", ContactField.TYPE_NUMBER)
        testers = self.create_group("Testers", contacts=[])
        doctors = self.create_group("Doctors", contacts=[])
        self.create_group("No Age", query='age = ""')

        # only static groups appear as options
        response = self.client.get(preview_url)
        self.assertEqual([doctors, testers], list(response.context["form"].fields["existing_group"].queryset))

        # try submitting without group
        response = self.client.post(preview_url, {"add_to_group": True, "group_mode": "E", "existing_group": ""})
        self.assertFormError(response.context["form"], "existing_group", "Required.")

        # finally try with actual group...
        response = self.client.post(
            preview_url, {"add_to_group": True, "group_mode": "E", "existing_group": doctors.id}
        )
        self.assertRedirect(response, read_url)

        imp.refresh_from_db()
        self.assertEqual(doctors, imp.group)

    @mock_mailroom
    def test_preview_with_mappings(self, mr_mocks):
        self.create_field("age", "Age", ContactField.TYPE_NUMBER)

        imp = self.create_contact_import("media/test_imports/extra_fields_and_group.xlsx")
        preview_url = reverse("contacts.contactimport_preview", args=[imp.id])

        self.assertRequestDisallowed(preview_url, [None, self.agent, self.admin2])

        # columns 4 and 5 are a non-existent field so will have controls to create a new one
        self.assertUpdateFetch(
            preview_url,
            [self.editor, self.admin],
            form_fields=[
                "add_to_group",
                "group_mode",
                "new_group_name",
                "existing_group",
                "column_5_include",
                "column_5_name",
                "column_5_value_type",
                "column_6_include",
                "column_6_name",
                "column_6_value_type",
            ],
        )

        # if including a new fields, can't use existing field name
        response = self.client.post(
            preview_url,
            {
                "column_5_include": True,
                "column_5_name": "Goats",
                "column_5_value_type": "N",
                "column_6_include": True,
                "column_6_name": "age",
                "column_6_value_type": "N",
                "add_to_group": False,
            },
        )
        self.assertEqual(1, len(response.context["form"].errors))
        self.assertFormError(response.context["form"], None, "Field name for 'Field:Sheep' matches an existing field.")

        # if including a new fields, can't repeat names
        response = self.client.post(
            preview_url,
            {
                "column_5_include": True,
                "column_5_name": "Goats",
                "column_5_value_type": "N",
                "column_6_include": True,
                "column_6_name": "goats",
                "column_6_value_type": "N",
                "add_to_group": False,
            },
        )
        self.assertEqual(1, len(response.context["form"].errors))
        self.assertFormError(response.context["form"], None, "Field name 'goats' is repeated.")

        # if including a new field, name can't be invalid
        response = self.client.post(
            preview_url,
            {
                "column_5_include": True,
                "column_5_name": "Goats",
                "column_5_value_type": "N",
                "column_6_include": True,
                "column_6_name": "#$%^@",
                "column_6_value_type": "N",
                "add_to_group": False,
            },
        )
        self.assertEqual(1, len(response.context["form"].errors))
        self.assertFormError(
            response.context["form"], None, "Field name for 'Field:Sheep' is invalid or a reserved word."
        )

        # or empty
        response = self.client.post(
            preview_url,
            {
                "column_5_include": True,
                "column_5_name": "Goats",
                "column_5_value_type": "N",
                "column_6_include": True,
                "column_6_name": "",
                "column_6_value_type": "T",
                "add_to_group": False,
            },
        )
        self.assertEqual(1, len(response.context["form"].errors))
        self.assertFormError(response.context["form"], None, "Field name for 'Field:Sheep' can't be empty.")

        # unless you're ignoring it
        response = self.client.post(
            preview_url,
            {
                "column_5_include": True,
                "column_5_name": "Goats",
                "column_5_value_type": "N",
                "column_6_include": False,
                "column_6_name": "",
                "column_6_value_type": "T",
                "add_to_group": False,
            },
        )
        self.assertEqual(302, response.status_code)

        # mappings will have been updated
        imp.refresh_from_db()
        self.assertEqual(
            [
                {"header": "URN:Tel", "mapping": {"type": "scheme", "scheme": "tel"}},
                {"header": "Name", "mapping": {"type": "attribute", "name": "name"}},
                {"header": "language", "mapping": {"type": "attribute", "name": "language"}},
                {"header": "Status", "mapping": {"type": "attribute", "name": "status"}},
                {"header": "Created On", "mapping": {"type": "ignore"}},
                {
                    "header": "field: goats",
                    "mapping": {"type": "new_field", "key": "goats", "name": "Goats", "value_type": "N"},
                },
                {"header": "Field:Sheep", "mapping": {"type": "ignore"}},
                {"header": "Group:Testers", "mapping": {"type": "ignore"}},
            ],
            imp.mappings,
        )

    @patch("temba.contacts.models.ContactImport.BATCH_SIZE", 2)
    @mock_mailroom
    def test_read(self, mr_mocks):
        imp = self.create_contact_import("media/test_imports/simple.xlsx")
        imp.start()

        read_url = reverse("contacts.contactimport_read", args=[imp.id])

        self.assertRequestDisallowed(read_url, [None, self.agent, self.admin2])
        self.assertReadFetch(read_url, [self.editor, self.admin], context_object=imp)

    @mock_mailroom
    def test_preview_with_field_limit_reached(self, mr_mocks):
        """Test that new fields are automatically ignored when field limit is reached"""
        # Create import with a file that has new fields
        imp = self.create_contact_import("media/test_imports/extra_fields_and_group.xlsx")

        preview_url = reverse("contacts.contactimport_preview", args=[imp.id])

        # Mock field limit as reached
        with patch("temba.contacts.models.ContactField.is_limit_reached", return_value=True):
            response = self.assertReadFetch(preview_url, [self.admin])

            # Check that new field checkboxes are disabled when limit is reached
            form = response.context["form"]
            new_field_columns = [col for col in form.columns if col["mapping"]["type"] == "new_field"]
            for column in new_field_columns:
                include_field_name = column["controls"][0]  # First control is the include checkbox
                include_field = form.fields[include_field_name]
                self.assertFalse(include_field.initial)  # Should be initially unchecked
                self.assertTrue(include_field.widget.attrs.get("disabled", False))  # Should be disabled

    @mock_mailroom
    def test_preview_with_field_limit_not_reached(self, mr_mocks):
        """Test that new fields are normally available when field limit is not reached"""
        # Create import with a file that has new fields
        imp = self.create_contact_import("media/test_imports/extra_fields_and_group.xlsx")

        preview_url = reverse("contacts.contactimport_preview", args=[imp.id])

        # Mock field limit as NOT reached
        with patch("temba.contacts.models.ContactField.is_limit_reached", return_value=False):
            response = self.assertReadFetch(preview_url, [self.admin])

            # Check that new field checkboxes are enabled when limit is not reached
            form = response.context["form"]
            new_field_columns = [col for col in form.columns if col["mapping"]["type"] == "new_field"]
            for column in new_field_columns:
                include_field_name = column["controls"][0]  # First control is the include checkbox
                include_field = form.fields[include_field_name]
                self.assertTrue(include_field.initial)  # Should be initially checked
                self.assertFalse(include_field.widget.attrs.get("disabled", False))  # Should not be disabled

    @mock_mailroom
    def test_preview_with_group_limit_reached(self, mr_mocks):
        """Test that new group option is hidden when group limit is reached"""

        imp = self.create_contact_import("media/test_imports/simple.xlsx")

        preview_url = reverse("contacts.contactimport_preview", args=[imp.id])

        # Mock group limit as reached
        with patch("temba.contacts.models.ContactGroup.is_limit_reached", return_value=True):
            response = self.assertReadFetch(preview_url, [self.admin])

            # Check that form only has existing group option
            form = response.context["form"]
            group_mode_choices = form.fields["group_mode"].choices
            self.assertEqual(len(group_mode_choices), 1)
            self.assertEqual(group_mode_choices[0][0], form.GROUP_MODE_EXISTING)

            # Initial value should be existing group mode
            self.assertEqual(form.fields["group_mode"].initial, form.GROUP_MODE_EXISTING)

    @mock_mailroom
    def test_field_limit_validation_prevents_circumvention(self, mr_mocks):
        """Test that backend validation prevents field limit circumvention"""
        imp = self.create_contact_import("media/test_imports/extra_fields_and_group.xlsx")

        preview_url = reverse("contacts.contactimport_preview", args=[imp.id])

        # Get the form to see what fields are available when limit not reached
        response = self.assertReadFetch(preview_url, [self.admin])
        form = response.context["form"]
        new_field_columns = [col for col in form.columns if col["mapping"]["type"] == "new_field"]

        # Set field limit to current count so we're at the limit
        current_field_count = imp.org.fields.filter(is_system=False, is_active=True).count()

        # Now try to submit with new field when at limit
        with override_settings(ORG_LIMIT_DEFAULTS={"fields": current_field_count, "groups": 10}):
            # Try to submit with new field included (trying to circumvent UI restrictions)
            post_data = {}
            if new_field_columns:
                # Include a new field in submission
                post_data["column_6_include"] = True
                post_data["column_6_name"] = "New Field"
                post_data["column_6_value_type"] = "T"

            response = self.client.post(preview_url, post_data)
            # Should get form errors due to field limit validation
            self.assertEqual(200, response.status_code)
            self.assertFormError(response.context["form"], None, "This workspace has reached its limit of fields.")
