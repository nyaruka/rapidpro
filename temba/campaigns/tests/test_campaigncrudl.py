from unittest.mock import call

from django.urls import reverse

from temba.campaigns.models import Campaign, CampaignEvent
from temba.tests import CRUDLTestMixin, TembaTest, mock_mailroom


class CampaignCRUDLTest(TembaTest, CRUDLTestMixin):
    def setUp(self):
        super().setUp()

        self.create_field("registered", "Registered", value_type="D")
        self.create_field("registered", "Registered", value_type="D", org=self.org2)

    def create_campaign(self, org, name, group):
        user = org.get_admins().first()
        registered = org.fields.get(key="registered")
        flow = self.create_flow(f"{name} Flow", org=org)
        campaign = Campaign.create(org, user, name, group)
        CampaignEvent.create_flow_event(
            org, user, campaign, registered, offset=1, unit="W", flow=flow, delivery_hour="13"
        )
        return campaign

    def test_menu(self):
        menu_url = reverse("campaigns.campaign_menu")

        group = self.create_group("My Group", contacts=[])
        self.create_campaign(self.org, "My Campaign", group)

        self.assertRequestDisallowed(menu_url, [None, self.agent])
        self.assertPageMenu(menu_url, self.admin, ["Active (1)", "Archived (0)"])

    def test_create(self):
        group = self.create_group("Reporters", contacts=[])

        create_url = reverse("campaigns.campaign_create")

        self.assertRequestDisallowed(create_url, [None, self.agent])
        self.assertCreateFetch(create_url, [self.editor, self.admin], form_fields=["name", "group"])

        # try to submit with no data
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {},
            form_errors={"name": "This field is required.", "group": "This field is required."},
        )

        # submit with valid data
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "Reminders", "group": group.id},
            new_obj_query=Campaign.objects.filter(name="Reminders", group=group),
        )

    def test_read(self):
        group = self.create_group("Reporters", contacts=[])
        campaign = self.create_campaign(self.org, "Welcomes", group)
        registered = self.org.fields.get(key="registered")
        CampaignEvent.create_flow_event(
            self.org, self.admin, campaign, registered, offset=0, unit="D", flow=self.create_flow("Event2Flow")
        )
        CampaignEvent.create_flow_event(
            self.org, self.admin, campaign, registered, offset=1, unit="H", flow=self.create_flow("Event3Flow")
        )

        read_url = reverse("campaigns.campaign_read", args=[campaign.uuid])

        self.assertRequestDisallowed(read_url, [None, self.agent, self.admin2])
        response = self.assertReadFetch(read_url, [self.editor, self.admin], context_object=campaign)
        self.assertContains(response, "Welcomes")
        self.assertContains(response, "Registered")
        self.assertContains(response, "Event2Flow")
        self.assertContains(response, "Event3Flow")

        self.assertContentMenu(read_url, self.admin, ["New Event", "Edit", "Export", "Archive"])

        campaign.archive(self.admin)

        self.assertContentMenu(read_url, self.admin, ["Activate", "Export", "-", "Delete"])

    def test_preview_read(self):
        group = self.create_group("Reporters", contacts=[])
        campaign = self.create_campaign(self.org, "Welcomes", group)

        read_url = reverse("campaigns.campaign_read", args=[campaign.uuid])

        self.login(self.admin)

        # default render is still the legacy table
        response = self.client.get(read_url)
        self.assertNotContains(response, "temba-campaign-events")
        self.assertIn("events", response.context)

        # entering preview mode swaps in the temba-campaign-events component which fetches the events itself
        self.client.cookies["temba-preview"] = "1"

        response = self.client.get(read_url)
        self.assertContains(response, "temba-campaign-events")
        self.assertContains(response, "Welcomes")
        self.assertNotIn("events", response.context)

    def test_events(self):
        group = self.create_group("Reporters", contacts=[])
        campaign = self.create_campaign(self.org, "Welcomes", group)
        registered = self.org.fields.get(key="registered")
        joined = self.create_field("joined", "Joined", value_type="D")

        flow_event = campaign.events.get()
        message_event = CampaignEvent.create_message_event(
            self.org,
            self.admin,
            campaign,
            registered,
            offset=-3,
            unit="D",
            translations={"eng": {"text": "Hi @fields.registered"}},
            base_language="eng",
            delivery_hour=9,
        )
        joined_event = CampaignEvent.create_flow_event(
            self.org, self.admin, campaign, joined, offset=0, unit="D", flow=flow_event.flow
        )

        events_url = reverse("campaigns.campaign_events", args=[campaign.uuid])

        self.assertRequestDisallowed(events_url, [None, self.agent, self.admin2])

        self.login(self.editor)

        # like the preview read page it feeds, the endpoint only exists in preview mode
        response = self.client.get(events_url)
        self.assertEqual(404, response.status_code)

        self.client.cookies["temba-preview"] = "1"
        response = self.client.get(events_url)
        self.assertEqual(200, response.status_code)

        # events are sorted by field name then offset, and carry the schedule definition rather than a computed time
        self.assertEqual(
            {
                "campaign": {"uuid": str(campaign.uuid), "name": "Welcomes"},
                "events": [
                    {
                        "uuid": str(joined_event.uuid),
                        "type": "flow",
                        "status": "ready",
                        "offset": 0,
                        "unit": "D",
                        "offset_display": "on",
                        "relative_to": {"key": "joined", "name": "Joined", "system": False},
                        "count": 0,
                        "edit_url": f"/campaignevent/update/{joined_event.uuid}/",
                        "delete_url": f"/campaignevent/delete/{joined_event.uuid}/",
                        "fires_url": f"/campaignevent/fires/{joined_event.uuid}/",
                        "flow": {
                            "uuid": str(flow_event.flow.uuid),
                            "name": "Welcomes Flow",
                            "url": f"/flow/editor/{flow_event.flow.uuid}/",
                        },
                    },
                    {
                        "uuid": str(message_event.uuid),
                        "type": "message",
                        "status": "ready",
                        "offset": -3,
                        "unit": "D",
                        "offset_display": "3 days before",
                        "delivery_hour_display": "at 9:00 a.m.",
                        "relative_to": {"key": "registered", "name": "Registered", "system": False},
                        "count": 0,
                        "edit_url": f"/campaignevent/update/{message_event.uuid}/",
                        "delete_url": f"/campaignevent/delete/{message_event.uuid}/",
                        "fires_url": f"/campaignevent/fires/{message_event.uuid}/",
                        "message": "Hi @fields.registered",
                    },
                    {
                        "uuid": str(flow_event.uuid),
                        "type": "flow",
                        "status": "ready",
                        "offset": 1,
                        "unit": "W",
                        "offset_display": "1 week after",
                        "delivery_hour_display": "at 1:00 p.m.",
                        "relative_to": {"key": "registered", "name": "Registered", "system": False},
                        "count": 0,
                        "edit_url": f"/campaignevent/update/{flow_event.uuid}/",
                        "delete_url": f"/campaignevent/delete/{flow_event.uuid}/",
                        "fires_url": f"/campaignevent/fires/{flow_event.uuid}/",
                        "flow": {
                            "uuid": str(flow_event.flow.uuid),
                            "name": "Welcomes Flow",
                            "url": f"/flow/editor/{flow_event.flow.uuid}/",
                        },
                    },
                ],
                "can_edit": True,
                "can_delete": True,
            },
            response.json(),
        )

    @mock_mailroom
    def test_update(self, mr_mocks):
        group1 = self.create_group("Reporters", contacts=[])
        group2 = self.create_group("Testers", query="tester=1")

        campaign = self.create_campaign(self.org, "Welcomes", group1)

        update_url = reverse("campaigns.campaign_update", args=[campaign.uuid])

        self.assertRequestDisallowed(update_url, [None, self.agent, self.admin2])
        self.assertUpdateFetch(
            update_url, [self.editor, self.admin], form_fields={"name": "Welcomes", "group": group1.id}
        )

        # try to submit with empty name
        self.assertUpdateSubmit(
            update_url,
            self.admin,
            {"name": "", "group": group1.id},
            form_errors={"name": "This field is required."},
            object_unchanged=campaign,
        )

        # submit with valid name
        self.assertUpdateSubmit(update_url, self.admin, {"name": "Greetings", "group": group1.id}, success_status=200)

        campaign.refresh_from_db()
        self.assertEqual("Greetings", campaign.name)
        self.assertEqual(group1, campaign.group)

        # won't have rescheduled the campaign's event for just a name change
        self.assertEqual([], mr_mocks.calls["campaign_schedule"])

        # submit with group change
        self.assertUpdateSubmit(update_url, self.admin, {"name": "Greetings", "group": group2.id}, success_status=200)

        campaign.refresh_from_db()
        self.assertEqual("Greetings", campaign.name)
        self.assertEqual(group2, campaign.group)

        # should have called mailroom reschedule the campaign's event
        self.assertEqual(
            [call(self.org, campaign.events.filter(is_active=True).get())], mr_mocks.calls["campaign_schedule"]
        )

        # can't update archived campaign
        campaign.archive(self.admin)

        self.assertRequestDisallowed(update_url, [self.admin])

    def test_delete(self):
        group = self.create_group("Reporters", contacts=[])
        campaign = self.create_campaign(self.org, "Welcomes", group)
        registered = self.org.fields.get(key="registered")
        CampaignEvent.create_flow_event(
            self.org, self.admin, campaign, registered, offset=0, unit="D", flow=self.create_flow("Event2Flow")
        )
        CampaignEvent.create_flow_event(
            self.org, self.admin, campaign, registered, offset=1, unit="H", flow=self.create_flow("Event3Flow")
        )

        self.assertEqual(Campaign.objects.filter(id=campaign.id, is_active=True).count(), 1)
        self.assertEqual(CampaignEvent.objects.filter(campaign=campaign, is_active=True).count(), 3)

        delete_url = reverse("campaigns.campaign_delete", args=[campaign.uuid])

        self.assertRequestDisallowed(delete_url, [None, self.agent, self.admin2])
        self.assertDeleteFetch(delete_url, [self.editor, self.admin], status=404)  # can't delete active campaign

        campaign.archive(self.admin)
        self.assertRequestDisallowed(delete_url, [None, self.agent, self.admin2])
        self.assertDeleteFetch(delete_url, [self.editor, self.admin])
        self.assertDeleteSubmit(delete_url, self.admin, object_deactivated=campaign)

        self.assertEqual(Campaign.objects.filter(id=campaign.id, is_active=True).count(), 0)
        self.assertEqual(CampaignEvent.objects.filter(campaign=campaign, is_active=True).count(), 0)

        self.assertEqual(Campaign.objects.filter(id=campaign.id, is_active=False).count(), 1)
        self.assertEqual(CampaignEvent.objects.filter(campaign=campaign, is_active=False).count(), 3)

    def test_list(self):
        list_url = reverse("campaigns.campaign_list")

        group = self.create_group("Reporters", contacts=[])
        campaign1 = self.create_campaign(self.org, "Welcomes", group)
        campaign2 = self.create_campaign(self.org, "Follow Ups", group)
        campaign3 = self.create_campaign(self.org, "Reminders", group)
        campaign3.archive(self.admin)

        other_org_group = self.create_group("Reporters", contacts=[], org=self.org2)
        self.create_campaign(self.org2, "Welcomes", other_org_group)

        self.assertRequestDisallowed(list_url, [None, self.agent])
        self.assertListFetch(list_url, [self.editor, self.admin], context_objects=[campaign2, campaign1])
        self.assertContentMenu(list_url, self.admin, ["New Campaign"])

    @mock_mailroom
    def test_preview_list(self, mr_mocks):
        group = self.create_group("Reporters", contacts=[])
        campaign1 = self.create_campaign(self.org, "Welcomes", group)
        campaign2 = self.create_campaign(self.org, "Follow Ups", group)

        list_url = reverse("campaigns.campaign_list")
        archived_url = reverse("campaigns.campaign_archived")

        self.login(self.admin)

        # default render is still the legacy table
        response = self.client.get(list_url)
        self.assertNotContains(response, "temba-campaign-list")

        # entering preview mode swaps in the temba-campaign-list component, pointed at the internal campaigns api
        self.client.cookies["temba-preview"] = "1"

        response = self.client.get(list_url)
        self.assertContains(response, "temba-campaign-list")
        self.assertEqual(
            f"{reverse('api.internal.campaigns')}.json?folder=active", response.context["new_list_endpoint"]
        )
        self.assertEqual(["archive"], [a["key"] for a in response.context["new_list_bulk_actions"]])

        # the archived view selects the archived folder and offers restore instead
        response = self.client.get(archived_url)
        self.assertEqual(
            f"{reverse('api.internal.campaigns')}.json?folder=archived", response.context["new_list_endpoint"]
        )
        self.assertNotEqual("", response.context["new_list_subtitle"])
        self.assertEqual(["restore"], [a["key"] for a in response.context["new_list_bulk_actions"]])

        # the component posts campaign uuids in `objects`; the view translates them to ids so the bulk action applies
        self.client.post(list_url, {"action": "archive", "objects": str(campaign1.uuid)})
        campaign1.refresh_from_db()
        self.assertTrue(campaign1.is_archived)

        # ...and restore works the same way from the archived view
        self.client.post(archived_url, {"action": "restore", "objects": str(campaign1.uuid)})
        campaign1.refresh_from_db()
        self.assertFalse(campaign1.is_archived)

        # a malformed uuid is dropped rather than erroring
        response = self.client.post(list_url, {"action": "archive", "objects": "not-a-uuid"})
        self.assertEqual(200, response.status_code)
        campaign2.refresh_from_db()
        self.assertFalse(campaign2.is_archived)

        # a campaign belonging to another org can't be touched
        other_org_group = self.create_group("Reporters", contacts=[], org=self.org2)
        other_org_campaign = self.create_campaign(self.org2, "Other Org", other_org_group)
        response = self.client.post(list_url, {"action": "archive", "objects": str(other_org_campaign.uuid)})
        self.assertEqual(200, response.status_code)
        other_org_campaign.refresh_from_db()
        self.assertFalse(other_org_campaign.is_archived)

    def test_archived(self):
        archived_url = reverse("campaigns.campaign_archived")

        group = self.create_group("Reporters", contacts=[])
        campaign1 = self.create_campaign(self.org, "Welcomes", group)
        campaign2 = self.create_campaign(self.org, "Follow Ups", group)
        self.create_campaign(self.org, "Reminders", group)

        other_org_group = self.create_group("Reporters", contacts=[], org=self.org2)
        self.create_campaign(self.org2, "Welcomes", other_org_group)

        campaign1.archive(self.admin)
        campaign2.archive(self.admin)

        self.assertRequestDisallowed(archived_url, [None, self.agent])
        self.assertListFetch(archived_url, [self.editor, self.admin], context_objects=[campaign2, campaign1])
        self.assertContentMenu(archived_url, self.admin, [])

    @mock_mailroom
    def test_archive_and_activate(self, mr_mocks):
        group = self.create_group("Reporters", contacts=[])
        campaign = self.create_campaign(self.org, "Welcomes", group)
        other_org_group = self.create_group("Reporters", contacts=[], org=self.org2)
        other_org_campaign = self.create_campaign(self.org2, "Welcomes", other_org_group)

        archive_url = reverse("campaigns.campaign_archive", args=[campaign.uuid])

        # can't archive campaign if not logged in
        response = self.client.post(archive_url)
        self.assertLoginRedirect(response)

        self.login(self.admin)

        response = self.client.post(archive_url)
        self.assertEqual(302, response.status_code)

        campaign.refresh_from_db()
        self.assertTrue(campaign.is_archived)

        # activate that archve
        response = self.client.post(reverse("campaigns.campaign_activate", args=[campaign.uuid]))
        self.assertEqual(302, response.status_code)

        campaign.refresh_from_db()
        self.assertFalse(campaign.is_archived)

        # can't archive campaign from other org
        response = self.client.post(reverse("campaigns.campaign_archive", args=[other_org_campaign.uuid]))
        self.assertEqual(404, response.status_code)

        # check object is unchanged
        other_org_campaign.refresh_from_db()
        self.assertFalse(other_org_campaign.is_archived)
