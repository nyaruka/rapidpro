from django.test.utils import override_settings
from django.urls import reverse

from temba.campaigns.models import Campaign, CampaignEvent
from temba.contacts.models import ContactField
from temba.tests import CRUDLTestMixin, TembaTest, mock_mailroom


class ContactFieldCRUDLTest(TembaTest, CRUDLTestMixin):
    def setUp(self):
        super().setUp()

        self.age = self.create_field("age", "Age", value_type="N", show_in_table=True)
        self.gender = self.create_field("gender", "Gender", value_type="T")
        self.state = self.create_field("state", "State", value_type="S")

        self.deleted = self.create_field("foo", "Foo")
        self.deleted.is_active = False
        self.deleted.save(update_fields=("is_active",))

        self.other_org_field = self.create_field("other", "Other", org=self.org2)

    def test_create(self):
        create_url = reverse("contacts.contactfield_create")

        self.assertRequestDisallowed(create_url, [None, self.agent])

        # for a deploy that doesn't have locations feature, don't show location field types
        with override_settings(FEATURES={}):
            response = self.assertCreateFetch(
                create_url,
                [self.editor, self.admin],
                form_fields=["name", "value_type", "agent_access"],
            )
            self.assertEqual(
                [("T", "Text"), ("N", "Number"), ("D", "Date & Time")],
                response.context["form"].fields["value_type"].choices,
            )

        response = self.assertCreateFetch(
            create_url,
            [self.editor, self.admin],
            form_fields=["name", "value_type", "agent_access"],
        )
        self.assertEqual(
            [("T", "Text"), ("N", "Number"), ("D", "Date & Time"), ("S", "State"), ("I", "District"), ("W", "Ward")],
            response.context["form"].fields["value_type"].choices,
        )

        # try to submit with empty name
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "", "value_type": "T", "agent_access": "E"},
            form_errors={"name": "This field is required."},
        )

        # try to submit with invalid name
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "???", "value_type": "T", "agent_access": "E"},
            form_errors={"name": "Can only contain letters, numbers and hypens."},
        )

        # try to submit with something that would be an invalid key
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "HAS", "value_type": "T", "agent_access": "E"},
            form_errors={"name": "Can't be a reserved word."},
        )

        # try to submit with name of existing field
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "AGE", "value_type": "N", "agent_access": "E"},
            form_errors={"name": "Must be unique."},
        )

        # submit with valid data - new fields always start unfeatured
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "Goats", "value_type": "N", "agent_access": "E"},
            new_obj_query=ContactField.user_fields.filter(
                org=self.org, name="Goats", value_type="N", show_in_table=False, agent_access="E"
            ),
            success_status=200,
        )

        # it's also ok to create a field with the same name as a deleted field
        ContactField.user_fields.get(key="age").release(self.admin)

        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "Age", "value_type": "N", "agent_access": "N"},
            new_obj_query=ContactField.user_fields.filter(
                org=self.org, name="Age", value_type="N", agent_access="N", is_active=True
            ),
            success_status=200,
        )

        # check we get the limit warning when we've reached the limit
        with override_settings(ORG_LIMIT_DEFAULTS={"fields": 2}):
            response = self.requestView(create_url, self.admin)
            self.assertContains(response, "You have reached the per-workspace limit")

    @mock_mailroom
    def test_update(self, mr_mocks):
        update_url = reverse("contacts.contactfield_update", args=[self.age.key])

        self.assertRequestDisallowed(update_url, [None, self.agent, self.admin2])

        # for a deploy that doesn't have locations feature, don't show location field types
        with override_settings(FEATURES={}):
            response = self.assertUpdateFetch(
                update_url,
                [self.editor, self.admin],
                form_fields={"name": "Age", "value_type": "N", "agent_access": "V"},
            )
            self.assertEqual(3, len(response.context["form"].fields["value_type"].choices))

        response = self.assertUpdateFetch(
            update_url,
            [self.editor, self.admin],
            form_fields={"name": "Age", "value_type": "N", "agent_access": "V"},
        )
        self.assertEqual(6, len(response.context["form"].fields["value_type"].choices))

        # try submit without change
        self.assertUpdateSubmit(
            update_url,
            self.admin,
            {"name": "Age", "value_type": "N", "agent_access": "V"},
            success_status=200,
        )

        # try to submit with empty name
        self.assertUpdateSubmit(
            update_url,
            self.admin,
            {"name": "", "value_type": "N", "agent_access": "V"},
            form_errors={"name": "This field is required."},
            object_unchanged=self.age,
        )

        # try to submit with invalid name
        self.assertUpdateSubmit(
            update_url,
            self.admin,
            {"name": "???", "value_type": "N", "agent_access": "V"},
            form_errors={"name": "Can only contain letters, numbers and hypens."},
            object_unchanged=self.age,
        )

        # try to submit with a name that is used by another field
        self.assertUpdateSubmit(
            update_url,
            self.admin,
            {"name": "GENDER", "value_type": "N", "agent_access": "V"},
            form_errors={"name": "Must be unique."},
            object_unchanged=self.age,
        )

        # submit with different name, type and agent access - featured state is untouched (it's
        # managed from the list page, not this form)
        self.assertUpdateSubmit(
            update_url,
            self.admin,
            {"name": "Age In Years", "value_type": "T", "agent_access": "E"},
            success_status=200,
        )

        self.age.refresh_from_db()
        self.assertEqual("Age In Years", self.age.name)
        self.assertEqual("T", self.age.value_type)
        self.assertTrue(self.age.show_in_table)
        self.assertEqual("E", self.age.agent_access)

        # simulate an org which has reached the limit for fields - should still be able to update a field
        with override_settings(ORG_LIMIT_DEFAULTS={"fields": 2}):
            self.assertUpdateSubmit(
                update_url,
                self.admin,
                {"name": "Age 2", "value_type": "T", "agent_access": "E"},
                success_status=200,
            )

        self.age.refresh_from_db()
        self.assertEqual("Age 2", self.age.name)

        # create a date field used in a campaign event
        registered = self.create_field("registered", "Registered", value_type="D")
        campaign = Campaign.create(self.org, self.admin, "Reminders", self.create_group("Farmers"))
        CampaignEvent.create_flow_event(
            self.org, self.admin, campaign, registered, offset=1, unit="W", flow=self.create_flow("Test")
        )

        update_url = reverse("contacts.contactfield_update", args=[registered.key])

        self.assertUpdateFetch(
            update_url,
            [self.editor, self.admin],
            form_fields={"name": "Registered", "value_type": "D", "agent_access": "V"},
        )

        # try to submit with different type
        self.assertUpdateSubmit(
            update_url,
            self.admin,
            {"name": "Registered", "value_type": "T", "agent_access": "V"},
            form_errors={"value_type": "Can't change type of date field being used by campaign events."},
            object_unchanged=registered,
        )

        # submit with only a different name
        self.assertUpdateSubmit(
            update_url,
            self.admin,
            {"name": "Registered On", "value_type": "D", "agent_access": "V"},
            success_status=200,
        )

        registered.refresh_from_db()
        self.assertEqual("Registered On", registered.name)
        self.assertEqual("D", registered.value_type)
        self.assertFalse(registered.show_in_table)

        # create a number field used in a query group
        birth = self.create_field("birth", "Birth", value_type="N")
        self.create_group("Smart Group", query="birth > 18")

        update_url = reverse("contacts.contactfield_update", args=[birth.key])

        self.assertUpdateFetch(
            update_url,
            [self.editor, self.admin],
            form_fields={"name": "Birth", "value_type": "N", "agent_access": "V"},
        )

        # try to submit with different type
        self.assertUpdateSubmit(
            update_url,
            self.admin,
            {"name": "Birth", "value_type": "T", "agent_access": "V"},
            form_errors={"value_type": "Can't change type of field being used by a smart group."},
            object_unchanged=birth,
        )

        # submit with only a different name
        self.assertUpdateSubmit(
            update_url,
            self.admin,
            {"name": "YearsOld", "value_type": "N", "agent_access": "V"},
            success_status=200,
        )
        birth.refresh_from_db()
        self.assertEqual("YearsOld", birth.name)
        self.assertEqual("N", birth.value_type)
        self.assertFalse(birth.show_in_table)

    def test_list(self):
        # opt into legacy mode to test the legacy list rendering
        self.setLegacyUI()

        list_url = reverse("contacts.contactfield_list")

        self.assertRequestDisallowed(list_url, [None, self.agent])
        self.assertListFetch(list_url, [self.editor, self.admin])
        self.assertContentMenu(list_url, self.editor, ["New"])
        self.assertContentMenu(list_url, self.admin, ["New"])

        with override_settings(ORG_LIMIT_DEFAULTS={"fields": 3}):
            response = self.assertListFetch(list_url, [self.admin])
            self.assertContains(response, "You have reached the per-workspace limit")
            self.assertContentMenu(list_url, self.admin, [])

    def test_new_list(self):
        list_url = reverse("contacts.contactfield_list")

        self.login(self.admin)

        # legacy mode renders the legacy field manager
        self.setLegacyUI()
        response = self.client.get(list_url)
        self.assertContains(response, "temba-field-manager")

        # by default we get the temba-field-list component which fetches the fields itself
        self.setLegacyUI(False)

        response = self.client.get(list_url)
        self.assertContains(response, "temba-field-list")
        self.assertNotContains(response, "temba-field-manager")

    @mock_mailroom
    def test_detail(self, mr_mocks):
        field = self.create_field("joined", "Joined", value_type="D")

        flow = self.create_flow("Flow")
        flow.field_dependencies.add(field)

        group = self.create_group("Farmers", query='joined != ""')
        campaign = Campaign.create(self.org, self.admin, "Planting Reminders", group)
        CampaignEvent.create_flow_event(
            self.org, self.admin, campaign, relative_to=field, offset=1, unit="W", flow=flow
        )

        detail_url = reverse("contacts.contactfield_detail", args=[field.key])

        self.assertRequestDisallowed(detail_url, [None, self.agent, self.admin2])

        self.login(self.editor)

        # like the new list page it feeds, the endpoint doesn't exist in legacy mode
        self.setLegacyUI()
        response = self.client.get(detail_url)
        self.assertEqual(404, response.status_code)

        self.setLegacyUI(False)
        response = self.client.get(detail_url)
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "field": {
                    "key": "joined",
                    "name": "Joined",
                    "value_type": "D",
                    "featured": False,
                    "agent_access": "V",
                },
                "usages": {
                    "flows": [{"uuid": str(flow.uuid), "name": "Flow", "url": f"/flow/editor/{flow.uuid}/"}],
                    "groups": [{"uuid": str(group.uuid), "name": "Farmers", "url": f"/contact/group/{group.uuid}/"}],
                    "campaign_events": [
                        {
                            "id": campaign.events.get().id,
                            "campaign": {
                                "uuid": str(campaign.uuid),
                                "name": "Planting Reminders",
                                "url": f"/campaign/read/{campaign.uuid}/",
                            },
                            "offset_display": "1 week after Joined",
                        }
                    ],
                },
                "counts": {"flows": 1, "groups": 1, "campaign_events": 1},
                "can_edit": True,
                "can_delete": True,
            },
            response.json(),
        )

        # a field with no dependents renders empty usages
        response = self.client.get(reverse("contacts.contactfield_detail", args=[self.gender.key]))
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {"flows": [], "groups": [], "campaign_events": []},
            response.json()["usages"],
        )

        # usages are capped but counts carry the full total
        for i in range(26):
            self.create_flow(f"Flow {i}").field_dependencies.add(self.gender)

        response = self.client.get(reverse("contacts.contactfield_detail", args=[self.gender.key]))
        self.assertEqual(25, len(response.json()["usages"]["flows"]))
        self.assertEqual(26, response.json()["counts"]["flows"])

        # system fields can't be edited or deleted
        response = self.client.get(reverse("contacts.contactfield_detail", args=["created_on"]))
        self.assertEqual(200, response.status_code)
        self.assertFalse(response.json()["can_edit"])
        self.assertFalse(response.json()["can_delete"])

    def test_update_priority(self):
        priority_url = reverse("contacts.contactfield_update_priority")

        self.assertRequestDisallowed(priority_url, [None, self.agent])

        self.login(self.admin)

        # the legacy shape is a map of key to priority
        response = self.client.post(priority_url, {"age": 10, "gender": 5, "other": 3}, content_type="application/json")
        self.assertEqual(200, response.status_code)

        self.age.refresh_from_db()
        self.gender.refresh_from_db()
        self.other_org_field.refresh_from_db()
        self.assertEqual(10, self.age.priority)
        self.assertEqual(5, self.gender.priority)
        self.assertEqual(0, self.other_org_field.priority)  # other org's field is unchanged

        # the new shape is the full ordered featured set - first is highest priority
        response = self.client.post(
            priority_url, {"featured": ["gender", "state", "other"]}, content_type="application/json"
        )
        self.assertEqual(200, response.status_code)

        self.age.refresh_from_db()
        self.gender.refresh_from_db()
        self.state.refresh_from_db()
        self.other_org_field.refresh_from_db()

        # listed fields are featured with descending priorities (unknown / cross-org keys ignored)
        self.assertTrue(self.gender.show_in_table)
        self.assertEqual(3, self.gender.priority)
        self.assertTrue(self.state.show_in_table)
        self.assertEqual(2, self.state.priority)
        self.assertFalse(self.other_org_field.show_in_table)

        # anything not listed is un-featured and zeroed
        self.assertFalse(self.age.show_in_table)
        self.assertEqual(0, self.age.priority)

        # an empty featured list un-features everything
        response = self.client.post(priority_url, {"featured": []}, content_type="application/json")
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, ContactField.user_fields.filter(org=self.org, is_active=True, show_in_table=True).count())

        # bad input is a 400
        response = self.client.post(priority_url, "notjson", content_type="application/json")
        self.assertEqual(400, response.status_code)

    @mock_mailroom
    def test_usages(self, mr_mocks):
        field = self.create_field("joined", "Joined", value_type="D")

        flow = self.create_flow("Flow")
        flow.field_dependencies.add(field)

        group = self.create_group("Farmers", query='joined != ""')
        campaign = Campaign.create(self.org, self.admin, "Planting Reminders", group)

        # create flow events
        event1 = CampaignEvent.create_flow_event(
            self.org,
            self.admin,
            campaign,
            relative_to=field,
            offset=0,
            unit="D",
            flow=flow,
            delivery_hour=17,
        )
        inactive_campaignevent = CampaignEvent.create_flow_event(
            self.org,
            self.admin,
            campaign,
            relative_to=field,
            offset=0,
            unit="D",
            flow=flow,
            delivery_hour=20,
        )
        inactive_campaignevent.is_active = False
        inactive_campaignevent.save(update_fields=("is_active",))

        usages_url = reverse("contacts.contactfield_usages", args=[field.key])

        self.assertRequestDisallowed(usages_url, [None, self.agent, self.admin2])
        response = self.assertReadFetch(usages_url, [self.editor, self.admin], context_object=field)

        self.assertEqual(
            {"flow": [flow], "group": [group], "campaign_event": [event1]},
            {t: list(qs) for t, qs in response.context["dependents"].items()},
        )

    def test_delete(self):
        # create new field 'Joined On' which is used by a campaign event (soft) and a flow (soft)
        group = self.create_group("Amazing Group", contacts=[])
        joined_on = self.create_field("joined_on", "Joined On", value_type=ContactField.TYPE_DATETIME)
        campaign = Campaign.create(self.org, self.admin, Campaign.get_unique_name(self.org, "Reminders"), group)
        flow = self.create_flow("Amazing Flow")
        flow.field_dependencies.add(joined_on)
        campaign_event = CampaignEvent.create_flow_event(
            self.org, self.admin, campaign, joined_on, offset=1, unit="W", flow=flow, delivery_hour=13
        )

        # make 'Age' appear to be used by a flow (soft) and a group (hard)
        flow.field_dependencies.add(self.age)
        group.query_fields.add(self.age)

        delete_gender_url = reverse("contacts.contactfield_delete", args=[self.gender.key])
        delete_joined_url = reverse("contacts.contactfield_delete", args=[joined_on.key])
        delete_age_url = reverse("contacts.contactfield_delete", args=[self.age.key])

        self.assertRequestDisallowed(delete_gender_url, [None, self.agent, self.admin2])

        # a field with no dependents can be deleted
        response = self.assertDeleteFetch(delete_gender_url, [self.editor, self.admin])
        self.assertEqual({}, response.context["soft_dependents"])
        self.assertEqual({}, response.context["hard_dependents"])
        self.assertContains(response, "You are about to delete")
        self.assertContains(response, "There is no way to undo this. Are you sure?")

        self.assertDeleteSubmit(delete_gender_url, self.admin, object_deactivated=self.gender, success_status=200)

        # create the same field again
        self.gender = self.create_field("gender", "Gender", value_type="T")

        # since fields are queried by key name, try and delete it again
        # to make sure we aren't deleting the previous deleted field again
        self.assertDeleteSubmit(delete_gender_url, self.admin, object_deactivated=self.gender, success_status=200)
        self.gender.refresh_from_db()
        self.assertFalse(self.gender.is_active)

        # a field with only soft dependents can also be deleted but we give warnings
        response = self.assertDeleteFetch(delete_joined_url, [self.admin])
        self.assertEqual({"flow", "campaign_event"}, set(response.context["soft_dependents"].keys()))
        self.assertEqual({}, response.context["hard_dependents"])
        self.assertContains(response, "is used by the following items but can still be deleted:")
        self.assertContains(response, "Amazing Flow")
        self.assertContains(response, "There is no way to undo this. Are you sure?")

        self.assertDeleteSubmit(delete_joined_url, self.admin, object_deactivated=joined_on, success_status=200)

        # check that flow is now marked as having issues
        flow.refresh_from_db()
        self.assertTrue(flow.has_issues)
        self.assertNotIn(joined_on, flow.field_dependencies.all())

        # and that the campaign event is gone
        campaign_event.refresh_from_db()
        self.assertFalse(campaign_event.is_active)

        # a field with hard dependents can't be deleted
        response = self.assertDeleteFetch(delete_age_url, [self.admin])
        self.assertEqual({"flow"}, set(response.context["soft_dependents"].keys()))
        self.assertEqual({"group"}, set(response.context["hard_dependents"].keys()))
        self.assertContains(response, "can't be deleted as it is still used by the following items:")
        self.assertContains(response, "Amazing Group")
        self.assertNotContains(response, "Delete")
