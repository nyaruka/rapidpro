from django.core import mail
from django.urls import reverse

from temba.orgs.models import Invitation, Org, OrgRole
from temba.tests import CRUDLTestMixin, TembaTest
from temba.tickets.models import Team


class InvitationCRUDLTest(TembaTest, CRUDLTestMixin):
    def test_list(self):
        list_url = reverse("orgs.invitation_list")

        # nobody can access if users feature not enabled
        response = self.requestView(list_url, self.admin)
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.org.features = [Org.FEATURE_USERS]
        self.org.save(update_fields=("features",))

        self.assertRequestDisallowed(list_url, [None, self.editor, self.agent])

        inv1 = Invitation.create(self.org, self.admin, "bob@textit.com", OrgRole.EDITOR)
        inv2 = Invitation.create(
            self.org, self.admin, "jim@textit.com", OrgRole.AGENT, team=self.org.default_ticket_team
        )

        response = self.assertListFetch(list_url, [self.admin], context_objects=[inv2, inv1])
        self.assertNotContains(response, "(All Topics)")

        self.org.features += [Org.FEATURE_TEAMS]
        self.org.save(update_fields=("features",))

        response = self.assertListFetch(list_url, [self.admin], context_objects=[inv2, inv1])
        self.assertContains(response, "(All Topics)")

    def test_create(self):
        create_url = reverse("orgs.invitation_create")

        # nobody can access if users feature not enabled
        response = self.requestView(create_url, self.admin)
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.org.features = [Org.FEATURE_CHILD_ORGS, Org.FEATURE_USERS]
        self.org.save(update_fields=("features",))

        self.assertRequestDisallowed(create_url, [None, self.agent, self.editor])
        self.assertCreateFetch(create_url, [self.admin], form_fields={"email": None, "role": "E"})

        # try submitting without email
        self.assertCreateSubmit(
            create_url, self.admin, {"email": "", "role": "E"}, form_errors={"email": "This field is required."}
        )

        # try submitting with invalid email
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"email": "@@@@", "role": "E"},
            form_errors={"email": "Enter a valid email address."},
        )

        # try submitting the email of an existing user (check is case-insensitive)
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"email": "EDITOR@textit.com", "role": "E"},
            form_errors={"email": "User is already a member of this workspace."},
        )

        # submit with valid email
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"email": "newguy@textit.com", "role": "A"},
            new_obj_query=Invitation.objects.filter(org=self.org, email="newguy@textit.com", role_code="A").exclude(
                secret=None
            ),
        )

        # check invitation email has been sent
        self.assertEqual(1, len(mail.outbox))

        # try submitting for same email again
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"email": "newguy@textit.com", "role": "E"},
            form_errors={"email": "User has already been invited to this workspace."},
        )

        # invite an agent (defaults to default team)
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"email": "newagent@textit.com", "role": "T"},
            new_obj_query=Invitation.objects.filter(
                org=self.org, email="newagent@textit.com", role_code="T", team=self.org.default_ticket_team
            ),
        )

        # if we have a teams feature, we can select a team
        self.org.features += [Org.FEATURE_TEAMS]
        self.org.save(update_fields=("features",))
        sales = Team.create(self.org, self.admin, "New Team", topics=[])

        self.assertCreateFetch(create_url, [self.admin], form_fields={"email": None, "role": "E", "team": None})
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"email": "otheragent@textit.com", "role": "T", "team": sales.id},
            new_obj_query=Invitation.objects.filter(
                org=self.org, email="otheragent@textit.com", role_code="T", team=sales
            ),
        )

    def test_delete(self):
        inv1 = Invitation.create(self.org, self.admin, "bob@textit.com", OrgRole.EDITOR)
        inv2 = Invitation.create(self.org, self.admin, "jim@textit.com", OrgRole.AGENT)

        delete_url = reverse("orgs.invitation_delete", args=[inv1.id])

        # nobody can access if users feature not enabled
        response = self.requestView(delete_url, self.admin)
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.org.features = [Org.FEATURE_USERS]
        self.org.save(update_fields=("features",))

        self.assertRequestDisallowed(delete_url, [None, self.editor, self.agent])

        response = self.assertDeleteFetch(delete_url, [self.admin], as_modal=True)
        self.assertContains(
            response, "You are about to cancel the invitation sent to <b>bob@textit.com</b>. Are you sure?"
        )

        response = self.assertDeleteSubmit(delete_url, self.admin, object_deactivated=inv1)

        self.assertRedirect(response, reverse("orgs.invitation_list"))
        self.assertEqual({inv2}, set(self.org.invitations.filter(is_active=True)))
