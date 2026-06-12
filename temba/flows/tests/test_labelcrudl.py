from django.urls import reverse

from temba.flows.models import FlowLabel
from temba.tests import CRUDLTestMixin, TembaTest


class FlowLabelCRUDLTest(TembaTest, CRUDLTestMixin):
    def test_create(self):
        create_url = reverse("flows.flowlabel_create")

        self.assertRequestDisallowed(create_url, [None, self.agent])
        self.assertCreateFetch(create_url, [self.editor, self.admin], form_fields=("name", "flows"))

        # try to submit without a name
        self.assertCreateSubmit(create_url, self.admin, {}, form_errors={"name": "This field is required."})

        # try to submit with an invalid name
        self.assertCreateSubmit(
            create_url, self.admin, {"name": '"Cool"\\'}, form_errors={"name": 'Cannot contain the character: "'}
        )

        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "Cool Flows"},
            new_obj_query=FlowLabel.objects.filter(org=self.org, name="Cool Flows"),
        )

        # try to create with a name that's already used
        self.assertCreateSubmit(create_url, self.admin, {"name": "Cool Flows"}, form_errors={"name": "Must be unique."})

        flow1 = self.create_flow("Flow 1")
        flow2 = self.create_flow("Flow 2")

        # the legacy list seeds the flows field with ids...
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "By Id", "flows": str(flow1.id)},
            new_obj_query=FlowLabel.objects.filter(org=self.org, name="By Id"),
        )
        self.assertEqual({flow1}, set(FlowLabel.objects.get(name="By Id").flows.all()))

        # ...the new (preview mode) list component with uuids — junk values are ignored
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "By UUID", "flows": f"{flow2.uuid},junk"},
            new_obj_query=FlowLabel.objects.filter(org=self.org, name="By UUID"),
        )
        self.assertEqual({flow2}, set(FlowLabel.objects.get(name="By UUID").flows.all()))

    def test_update(self):
        label = FlowLabel.create(self.org, self.admin, "Cool Flows")
        FlowLabel.create(self.org, self.admin, "Crazy Flows")

        update_url = reverse("flows.flowlabel_update", args=[label.id])

        self.assertRequestDisallowed(update_url, [None, self.agent, self.admin2])
        self.assertUpdateFetch(update_url, [self.editor, self.admin], form_fields=("name", "flows"))

        # try to update to an invalid name
        self.assertUpdateSubmit(
            update_url,
            self.admin,
            {"name": '"Cool"\\'},
            form_errors={"name": 'Cannot contain the character: "'},
            object_unchanged=label,
        )

        # try to update to a non-unique name
        self.assertUpdateSubmit(
            update_url,
            self.admin,
            {"name": "Crazy Flows"},
            form_errors={"name": "Must be unique."},
            object_unchanged=label,
        )

        self.assertUpdateSubmit(update_url, self.admin, {"name": "Super Cool Flows"})

        label.refresh_from_db()
        self.assertEqual("Super Cool Flows", label.name)

    def test_delete(self):
        label = FlowLabel.create(self.org, self.admin, "Cool Flows")

        delete_url = reverse("flows.flowlabel_delete", args=[label.id])

        self.assertRequestDisallowed(delete_url, [None, self.agent, self.admin2])

        self.assertDeleteFetch(delete_url, [self.editor, self.admin])
        self.assertDeleteSubmit(delete_url, self.admin, object_deleted=label, success_status=200)
