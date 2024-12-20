from django.test.utils import override_settings
from django.urls import reverse

from temba.orgs.models import Invitation, Org, OrgRole
from temba.tests import CRUDLTestMixin, TembaTest
from temba.tickets.models import Team, Topic


class TeamCRUDLTest(TembaTest, CRUDLTestMixin):
    @override_settings(ORG_LIMIT_DEFAULTS={"teams": 1})
    def test_create(self):
        create_url = reverse("tickets.team_create")

        # nobody can access if new orgs feature not enabled
        response = self.requestView(create_url, self.admin)
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.org.features = [Org.FEATURE_TEAMS]
        self.org.save(update_fields=("features",))

        self.assertRequestDisallowed(create_url, [None, self.agent, self.user, self.editor])

        self.assertCreateFetch(create_url, [self.admin], form_fields=("name", "topics"))

        sales = Topic.create(self.org, self.admin, "Sales")
        for n in range(Team.max_topics + 1):
            Topic.create(self.org, self.admin, f"Topic {n}")

        # try to create with empty values
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "", "topics": []},
            form_errors={"name": "This field is required."},
        )

        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "all topics", "topics": []},
            form_errors={"name": "Team with this name already exists."},
        )

        # try to create with name that has invalid characters
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "\\ministry", "topics": []},
            form_errors={"name": "Cannot contain the character: \\"},
        )

        # try to create with name that is too long
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "X" * 65, "topics": []},
            form_errors={"name": "Ensure this value has at most 64 characters (it has 65)."},
        )

        # try to create with too many topics
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "Everything", "topics": [t.id for t in self.org.topics.all()]},
            form_errors={"topics": "Teams can have at most 10 topics."},
        )

        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "Sales", "topics": [sales.id]},
            new_obj_query=Team.objects.filter(name="Sales", is_system=False),
            success_status=302,
        )

        team = Team.objects.get(name="Sales")
        self.assertEqual({sales}, set(team.topics.all()))

        # try to create another now that we've reached the limit
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "Training", "topics": [sales.id]},
            form_errors={
                "__all__": "This workspace has reached its limit of 1 teams. You must delete existing ones before you can create new ones."
            },
        )

    def test_update(self):
        sales = Topic.create(self.org, self.admin, "Sales")
        marketing = Topic.create(self.org, self.admin, "Marketing")
        team = Team.create(self.org, self.admin, "Sales", topics=[sales])

        update_url = reverse("tickets.team_update", args=[team.id])

        self.assertRequestDisallowed(update_url, [None, self.user, self.agent, self.editor, self.admin2])

        self.assertUpdateFetch(update_url, [self.admin], form_fields=["name", "topics"])

        # names must be unique (case-insensitive)
        self.assertUpdateSubmit(
            update_url,
            self.admin,
            {"name": "all topics"},
            form_errors={"name": "Team with this name already exists."},
            object_unchanged=team,
        )

        self.assertUpdateSubmit(
            update_url, self.admin, {"name": "Marketing", "topics": [marketing.id]}, success_status=302
        )

        team.refresh_from_db()
        self.assertEqual(team.name, "Marketing")
        self.assertEqual({marketing}, set(team.topics.all()))

        # can't edit a system team
        self.assertRequestDisallowed(
            reverse("tickets.team_update", args=[self.org.default_ticket_team.id]), [self.admin]
        )

    def test_delete(self):
        sales = Topic.create(self.org, self.admin, "Sales")
        team1 = Team.create(self.org, self.admin, "Sales", topics=[sales])
        team2 = Team.create(self.org, self.admin, "Other", topics=[sales])
        self.org.add_user(self.agent, OrgRole.AGENT, team=team1)
        invite = Invitation.create(self.org, self.admin, "newagent@textit.com", OrgRole.AGENT, team=team1)

        delete_url = reverse("tickets.team_delete", args=[team1.id])

        self.assertRequestDisallowed(delete_url, [None, self.user, self.agent, self.editor, self.admin2])

        # deleting blocked for team with agents
        response = self.assertDeleteFetch(delete_url, [self.admin])
        self.assertContains(response, "Sorry, the <b>Sales</b> team can't be deleted while it still has agents")

        self.org.add_user(self.agent, OrgRole.AGENT, team=team2)

        # deleting blocked for team with pending invitations
        response = self.assertDeleteFetch(delete_url, [self.admin])
        self.assertContains(
            response, "Sorry, the <b>Sales</b> team can't be deleted while it still has pending invitations"
        )

        invite.release()

        # try again...
        response = self.assertDeleteFetch(delete_url, [self.admin])
        self.assertContains(response, "You are about to delete the <b>Sales</b> team")

        response = self.assertDeleteSubmit(delete_url, self.admin, object_deactivated=team1, success_status=302)

        # other team unafected
        team2.refresh_from_db()
        self.assertTrue(team2.is_active)

        # we should have been redirected to the team list
        self.assertEqual("/team/", response.url)

    def test_list(self):
        sales = Topic.create(self.org, self.admin, "Sales")
        team1 = Team.create(self.org, self.admin, "Sales", topics=[sales])
        team2 = Team.create(self.org, self.admin, "Other", topics=[sales])
        Team.create(self.org2, self.admin2, "Cars", topics=[])

        list_url = reverse("tickets.team_list")

        # nobody can access if new orgs feature not enabled
        response = self.requestView(list_url, self.admin)
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.org.features = [Org.FEATURE_TEAMS]
        self.org.save(update_fields=("features",))

        self.assertRequestDisallowed(list_url, [None, self.agent, self.editor])

        self.assertListFetch(list_url, [self.admin], context_objects=[self.org.default_ticket_team, team2, team1])
