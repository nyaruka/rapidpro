from datetime import date, timedelta
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone

from temba.orgs.models import Export, OrgRole
from temba.tests import CRUDLTestMixin, TembaTest, matchers, mock_mailroom
from temba.tickets.models import Team, Ticket, TicketEvent, TicketExport, Topic
from temba.utils.dates import datetime_to_timestamp
from temba.utils.uuid import uuid4


class TicketCRUDLTest(TembaTest, CRUDLTestMixin):
    def setUp(self):
        super().setUp()

        self.contact = self.create_contact("Bob", urns=["twitter:bobby"])
        self.sales = Topic.create(self.org, self.admin, "Sales")
        self.support = Topic.create(self.org, self.admin, "Support")

        # create other agent users in teams with limited topic access
        self.agent2 = self.create_user("agent2@textit.com")
        sales_only = Team.create(self.org, self.admin, "Sales", topics=[self.sales])
        self.org.add_user(self.agent2, OrgRole.AGENT, team=sales_only)

        self.agent3 = self.create_user("agent3@textit.com")
        support_only = Team.create(self.org, self.admin, "Support", topics=[self.support])
        self.org.add_user(self.agent3, OrgRole.AGENT, team=support_only)

    def test_list(self):
        list_url = reverse("tickets.ticket_list")

        ticket = self.create_ticket(self.contact, assignee=self.admin, topic=self.support)

        # just a placeholder view for frontend components
        self.assertRequestDisallowed(list_url, [None])
        self.assertListFetch(
            list_url, [self.user, self.editor, self.admin, self.agent, self.agent2, self.agent3], context_objects=[]
        )

        # link to our ticket within the All folder
        deep_link = f"{list_url}all/open/{ticket.uuid}/"

        response = self.assertListFetch(
            deep_link, [self.user, self.editor, self.admin, self.agent, self.agent3], context_objects=[]
        )
        self.assertEqual("All", response.context["title"])
        self.assertEqual("all", response.context["folder"])
        self.assertEqual("open", response.context["status"])

        # our ticket exists on the first page, so it'll get flagged to be focused
        self.assertEqual(str(ticket.uuid), response.context["nextUUID"])

        # we have a specific ticket so we should show context menu for it
        self.assertContentMenu(deep_link, self.admin, ["Edit", "Add Note", "Start Flow"])

        with self.assertNumQueries(11):
            self.client.get(deep_link)

        # try same request but for agent that can't see this ticket
        response = self.assertListFetch(deep_link, [self.agent2], context_objects=[])
        self.assertEqual("All", response.context["title"])
        self.assertEqual("all", response.context["folder"])
        self.assertEqual("open", response.context["status"])
        self.assertNotIn("nextUUID", response.context)

        # can also link to our ticket within the Support topic
        deep_link = f"{list_url}{self.support.uuid}/open/{ticket.uuid}/"

        self.assertRequestDisallowed(deep_link, [self.agent2])  # doesn't have access to that topic

        response = self.assertListFetch(
            deep_link, [self.user, self.editor, self.admin, self.agent, self.agent3], context_objects=[]
        )
        self.assertEqual("Support", response.context["title"])
        self.assertEqual(str(self.support.uuid), response.context["folder"])
        self.assertEqual("open", response.context["status"])

        # try to link to our ticket but with mismatched topic
        deep_link = f"{list_url}{self.sales.uuid}/closed/{str(ticket.uuid)}/"

        # redirected to All
        response = self.assertListFetch(deep_link, [self.agent], context_objects=[])
        self.assertEqual("all", response.context["folder"])
        self.assertEqual("open", response.context["status"])
        self.assertEqual(str(ticket.uuid), response.context["uuid"])

        # try to link to our ticket but with mismatched status
        deep_link = f"{list_url}all/closed/{ticket.uuid}/"

        # now our ticket is listed as the uuid and we were redirected to All folder with Open status
        response = self.assertListFetch(deep_link, [self.agent], context_objects=[])
        self.assertEqual("all", response.context["folder"])
        self.assertEqual("open", response.context["status"])
        self.assertEqual(str(ticket.uuid), response.context["uuid"])

        # and again we have a specific ticket so we should show context menu for it
        self.assertContentMenu(deep_link, self.admin, ["Edit", "Add Note", "Start Flow"])

        # non-existent topic should give a 404
        bad_topic_link = f"{list_url}{uuid4()}/open/{ticket.uuid}/"
        response = self.requestView(bad_topic_link, self.agent)
        self.assertEqual(404, response.status_code)

        response = self.client.get(
            list_url,
            content_type="application/json",
            HTTP_X_TEMBA_REFERER_PATH=f"/tickets/mine/open/{ticket.uuid}",
        )
        self.assertEqual(("tickets", "mine", "open", str(ticket.uuid)), response.context["temba_referer"])

        # contacts in a flow don't get a start flow option
        flow = self.create_flow("Test")
        self.contact.current_flow = flow
        self.contact.save()
        deep_link = f"{list_url}all/open/{str(ticket.uuid)}/"
        self.assertContentMenu(deep_link, self.admin, ["Edit", "Add Note"])

        # closed our tickets don't get extra menu options
        ticket.status = Ticket.STATUS_CLOSED
        ticket.save(update_fields=("status",))
        deep_link = f"{list_url}all/closed/{str(ticket.uuid)}/"
        self.assertContentMenu(deep_link, self.admin, [])

    def test_update(self):
        ticket = self.create_ticket(self.contact, assignee=self.admin)

        update_url = reverse("tickets.ticket_update", args=[ticket.uuid])

        self.assertRequestDisallowed(update_url, [None, self.user, self.admin2])
        self.assertUpdateFetch(update_url, [self.agent, self.editor, self.admin], form_fields=["topic"])

        user_topic = Topic.objects.create(org=self.org, name="Hot Topic", created_by=self.admin, modified_by=self.admin)

        # edit successfully
        self.assertUpdateSubmit(update_url, self.admin, {"topic": user_topic.id}, success_status=302)

        ticket.refresh_from_db()
        self.assertEqual(user_topic, ticket.topic)

    def test_menu(self):
        menu_url = reverse("tickets.ticket_menu")

        self.create_ticket(self.contact, assignee=self.admin)
        self.create_ticket(self.contact, assignee=self.admin, topic=self.sales)
        self.create_ticket(self.contact, assignee=None)
        self.create_ticket(self.contact, closed_on=timezone.now())

        self.assertRequestDisallowed(menu_url, [None])
        self.assertPageMenu(
            menu_url,
            self.admin,
            [
                "My Tickets (2)",
                "Unassigned (1)",
                "All (3)",
                "Shortcuts (0)",
                "Export",
                "New Topic",
                "General (2)",
                "Sales (1)",
                "Support (0)",
            ],
        )
        self.assertPageMenu(
            menu_url,
            self.agent,
            ["My Tickets (0)", "Unassigned (1)", "All (3)", "General (2)", "Sales (1)", "Support (0)"],
        )
        self.assertPageMenu(menu_url, self.agent2, ["My Tickets (0)", "Unassigned (0)", "All (1)", "Sales (1)"])
        self.assertPageMenu(menu_url, self.agent3, ["My Tickets (0)", "Unassigned (0)", "All (0)", "Support (0)"])

    @mock_mailroom
    def test_folder(self, mr_mocks):
        self.login(self.admin)

        user_topic = Topic.objects.create(org=self.org, name="Hot Topic", created_by=self.admin, modified_by=self.admin)

        contact1 = self.create_contact("Joe", phone="123", last_seen_on=timezone.now())
        contact2 = self.create_contact("Frank", phone="124", last_seen_on=timezone.now())
        contact3 = self.create_contact("Anne", phone="125", last_seen_on=timezone.now())
        self.create_contact("Mary No tickets", phone="126", last_seen_on=timezone.now())
        self.create_contact("Mr Other Org", phone="126", last_seen_on=timezone.now(), org=self.org2)
        topic = Topic.objects.filter(org=self.org, is_system=True).first()

        open_url = reverse("tickets.ticket_folder", kwargs={"folder": "all", "status": "open"})
        closed_url = reverse("tickets.ticket_folder", kwargs={"folder": "all", "status": "closed"})
        mine_url = reverse("tickets.ticket_folder", kwargs={"folder": "mine", "status": "open"})
        unassigned_url = reverse("tickets.ticket_folder", kwargs={"folder": "unassigned", "status": "open"})
        system_topic_url = reverse("tickets.ticket_folder", kwargs={"folder": topic.uuid, "status": "open"})
        user_topic_url = reverse("tickets.ticket_folder", kwargs={"folder": user_topic.uuid, "status": "open"})
        bad_topic_url = reverse("tickets.ticket_folder", kwargs={"folder": uuid4(), "status": "open"})

        def assert_tickets(resp, tickets: list):
            actual_tickets = [t["ticket"]["uuid"] for t in resp.json()["results"]]
            expected_tickets = [str(t.uuid) for t in tickets]
            self.assertEqual(expected_tickets, actual_tickets)

        # system topic has no menu options
        self.assertContentMenu(system_topic_url, self.admin, [])

        # user topic gets edit too
        self.assertContentMenu(user_topic_url, self.admin, ["Edit", "Delete"])

        # no tickets yet so no contacts returned
        response = self.client.get(open_url)
        assert_tickets(response, [])

        # contact 1 has two open tickets and some messages
        c1_t1 = self.create_ticket(contact1)
        # assign it
        c1_t1.assign(self.admin, assignee=self.admin)
        c1_t2 = self.create_ticket(contact1)
        self.create_incoming_msg(contact1, "I have an issue")
        self.create_outgoing_msg(contact1, "We can help", created_by=self.admin)

        # contact 2 has an open ticket and a closed ticket
        c2_t1 = self.create_ticket(contact2)
        c2_t2 = self.create_ticket(contact2, closed_on=timezone.now())

        self.create_incoming_msg(contact2, "Anyone there?")
        self.create_incoming_msg(contact2, "Hello?")

        # contact 3 has two closed tickets
        c3_t1 = self.create_ticket(contact3, closed_on=timezone.now())
        c3_t2 = self.create_ticket(contact3, closed_on=timezone.now())

        self.create_outgoing_msg(contact3, "Yes", created_by=self.agent)

        # fetching open folder returns all open tickets
        with self.assertNumQueries(12):
            response = self.client.get(open_url)

        assert_tickets(response, [c2_t1, c1_t2, c1_t1])

        joes_open_tickets = contact1.tickets.filter(status="O").order_by("-opened_on")

        expected_json = {
            "results": [
                {
                    "uuid": str(contact2.uuid),
                    "name": "Frank",
                    "last_seen_on": matchers.ISODate(),
                    "last_msg": {
                        "text": "Hello?",
                        "direction": "I",
                        "type": "T",
                        "created_on": matchers.ISODate(),
                        "sender": None,
                        "attachments": [],
                    },
                    "ticket": {
                        "uuid": str(contact2.tickets.filter(status="O").first().uuid),
                        "assignee": None,
                        "topic": {"uuid": matchers.UUID4String(), "name": "General"},
                        "last_activity_on": matchers.ISODate(),
                        "closed_on": None,
                    },
                },
                {
                    "uuid": str(contact1.uuid),
                    "name": "Joe",
                    "last_seen_on": matchers.ISODate(),
                    "last_msg": {
                        "text": "We can help",
                        "direction": "O",
                        "type": "T",
                        "created_on": matchers.ISODate(),
                        "sender": {"id": self.admin.id, "email": "admin@textit.com"},
                        "attachments": [],
                    },
                    "ticket": {
                        "uuid": str(joes_open_tickets[0].uuid),
                        "assignee": None,
                        "topic": {"uuid": matchers.UUID4String(), "name": "General"},
                        "last_activity_on": matchers.ISODate(),
                        "closed_on": None,
                    },
                },
                {
                    "uuid": str(contact1.uuid),
                    "name": "Joe",
                    "last_seen_on": matchers.ISODate(),
                    "last_msg": {
                        "text": "We can help",
                        "direction": "O",
                        "type": "T",
                        "created_on": matchers.ISODate(),
                        "sender": {"id": self.admin.id, "email": "admin@textit.com"},
                        "attachments": [],
                    },
                    "ticket": {
                        "uuid": str(joes_open_tickets[1].uuid),
                        "assignee": {
                            "id": self.admin.id,
                            "first_name": "Andy",
                            "last_name": "",
                            "email": "admin@textit.com",
                        },
                        "topic": {"uuid": matchers.UUID4String(), "name": "General"},
                        "last_activity_on": matchers.ISODate(),
                        "closed_on": None,
                    },
                },
            ]
        }
        self.assertEqual(expected_json, response.json())

        # test before and after windowing
        response = self.client.get(f"{open_url}?before={datetime_to_timestamp(c2_t1.last_activity_on)}")
        self.assertEqual(2, len(response.json()["results"]))

        response = self.client.get(f"{open_url}?after={datetime_to_timestamp(c1_t2.last_activity_on)}")
        self.assertEqual(1, len(response.json()["results"]))

        # the two unassigned tickets
        response = self.client.get(unassigned_url)
        assert_tickets(response, [c2_t1, c1_t2])

        # one assigned ticket for mine
        response = self.client.get(mine_url)
        assert_tickets(response, [c1_t1])

        # three tickets for our general topic
        response = self.client.get(system_topic_url)
        assert_tickets(response, [c2_t1, c1_t2, c1_t1])

        # bad topic should be a 404
        response = self.client.get(bad_topic_url)
        self.assertEqual(response.status_code, 404)

        # fetching closed folder returns all closed tickets
        response = self.client.get(closed_url)
        assert_tickets(response, [c3_t2, c3_t1, c2_t2])
        self.assertEqual(
            {
                "uuid": str(contact3.uuid),
                "name": "Anne",
                "last_seen_on": matchers.ISODate(),
                "last_msg": {
                    "text": "Yes",
                    "direction": "O",
                    "type": "T",
                    "created_on": matchers.ISODate(),
                    "sender": {"id": self.agent.id, "email": "agent@textit.com"},
                    "attachments": [],
                },
                "ticket": {
                    "uuid": str(c3_t2.uuid),
                    "assignee": None,
                    "topic": {"uuid": matchers.UUID4String(), "name": "General"},
                    "last_activity_on": matchers.ISODate(),
                    "closed_on": matchers.ISODate(),
                },
            },
            response.json()["results"][0],
        )

        # deep linking to a single ticket returns just that ticket
        response = self.client.get(f"{open_url}{str(c1_t1.uuid)}")
        assert_tickets(response, [c1_t1])

        # make sure when paging we get a next url
        with patch("temba.tickets.views.TicketCRUDL.Folder.paginate_by", 1):
            response = self.client.get(open_url + "?_format=json")
            self.assertIsNotNone(response.json()["next"])

        # requesting my tickets as servicing staff should return empty list
        response = self.requestView(mine_url, self.customer_support, choose_org=self.org)
        assert_tickets(response, [])

        response = self.requestView(unassigned_url, self.customer_support, choose_org=self.org)
        assert_tickets(response, [c2_t1, c1_t2])

    @mock_mailroom
    def test_note(self, mr_mocks):
        ticket = self.create_ticket(self.contact)

        update_url = reverse("tickets.ticket_note", args=[ticket.uuid])

        self.assertRequestDisallowed(update_url, [None, self.user, self.admin2])
        self.assertUpdateFetch(update_url, [self.agent, self.editor, self.admin], form_fields=["note"])

        self.assertUpdateSubmit(
            update_url,
            self.admin,
            {"note": ""},
            form_errors={"note": "This field is required."},
            object_unchanged=ticket,
        )

        self.assertUpdateSubmit(
            update_url, self.admin, {"note": "I have a bad feeling about this."}, success_status=200
        )

        self.assertEqual(1, ticket.events.filter(event_type=TicketEvent.TYPE_NOTE_ADDED).count())

    def test_export_stats(self):
        export_url = reverse("tickets.ticket_export_stats")

        self.login(self.admin)

        response = self.client.get(export_url)
        self.assertEqual(200, response.status_code)
        self.assertEqual("application/ms-excel", response["Content-Type"])
        self.assertEqual(
            f"attachment; filename=ticket-stats-{timezone.now().strftime('%Y-%m-%d')}.xlsx",
            response["Content-Disposition"],
        )

    @mock_mailroom
    def test_export(self, mr_mocks):
        export_url = reverse("tickets.ticket_export")

        self.assertRequestDisallowed(export_url, [None, self.agent])
        response = self.assertUpdateFetch(
            export_url,
            [self.user, self.editor, self.admin],
            form_fields=("start_date", "end_date", "with_fields", "with_groups"),
        )
        self.assertNotContains(response, "already an export in progress")

        # create a dummy export task so that we won't be able to export
        blocking_export = TicketExport.create(
            self.org, self.admin, start_date=date.today() - timedelta(days=7), end_date=date.today()
        )

        response = self.client.get(export_url)
        self.assertContains(response, "already an export in progress")

        # check we can't submit in case a user opens the form and whilst another user is starting an export
        response = self.client.post(export_url, {"start_date": "2022-06-28", "end_date": "2022-09-28"})
        self.assertContains(response, "already an export in progress")
        self.assertEqual(1, Export.objects.count())

        # mark that one as finished so it's no longer a blocker
        blocking_export.status = Export.STATUS_COMPLETE
        blocking_export.save(update_fields=("status",))

        # try to submit with no values
        response = self.client.post(export_url, {})
        self.assertFormError(response.context["form"], "start_date", "This field is required.")
        self.assertFormError(response.context["form"], "end_date", "This field is required.")

        # try to submit with start date in future
        response = self.client.post(export_url, {"start_date": "2200-01-01", "end_date": "2022-09-28"})
        self.assertFormError(response.context["form"], None, "Start date can't be in the future.")

        # try to submit with start date > end date
        response = self.client.post(export_url, {"start_date": "2022-09-01", "end_date": "2022-03-01"})
        self.assertFormError(response.context["form"], None, "End date can't be before start date.")

        # try to submit with too many fields or groups
        too_many_fields = [self.create_field(f"Field {i}", f"field{i}") for i in range(11)]
        too_many_groups = [self.create_group(f"Group {i}", contacts=[]) for i in range(11)]

        response = self.client.post(
            export_url,
            {
                "start_date": "2022-06-28",
                "end_date": "2022-09-28",
                "with_fields": [cf.id for cf in too_many_fields],
                "with_groups": [cg.id for cg in too_many_groups],
            },
        )
        self.assertFormError(response.context["form"], "with_fields", "You can only include up to 10 fields.")
        self.assertFormError(response.context["form"], "with_groups", "You can only include up to 10 groups.")

        testers = self.create_group("Testers", contacts=[])
        gender = self.create_field("gender", "Gender")

        response = self.client.post(
            export_url,
            {
                "start_date": "2022-06-28",
                "end_date": "2022-09-28",
                "with_groups": [testers.id],
                "with_fields": [gender.id],
            },
        )
        self.assertEqual(200, response.status_code)

        export = Export.objects.exclude(id=blocking_export.id).get()
        self.assertEqual("ticket", export.export_type)
        self.assertEqual(date(2022, 6, 28), export.start_date)
        self.assertEqual(date(2022, 9, 28), export.end_date)
        self.assertEqual(
            {"with_groups": [testers.id], "with_fields": [gender.id]},
            export.config,
        )
