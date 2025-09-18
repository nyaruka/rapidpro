from allauth.mfa.models import Authenticator

from django.contrib.auth.models import Group
from django.urls import reverse

from temba.contacts.models import Contact
from temba.orgs.models import Org, OrgMembership, OrgRole
from temba.tests import CRUDLTestMixin, TembaTest, mock_mailroom
from temba.utils.views.mixins import TEMBA_MENU_SELECTION


class OrgCRUDLTest(TembaTest, CRUDLTestMixin):
    def test_read(self):
        read_url = reverse("staff.org_read", args=[self.org.id])

        # make our second org a child
        self.org2.parent = self.org
        self.org2.save()

        response = self.assertStaffOnly(read_url)

        # we should have a child in our context
        self.assertEqual(1, len(response.context["children"]))

        # we should have options to flag and suspend
        self.assertContentMenu(read_url, self.customer_support, ["Edit", "Flag", "Suspend", "Verify", "-", "Service"])

        # flag and content menu option should be inverted
        self.org.flag()
        self.org.suspend()

        self.assertContentMenu(
            read_url, self.customer_support, ["Edit", "Unflag", "Unsuspend", "Verify", "-", "Service"]
        )

        # no menu for inactive orgs
        self.org.is_active = False
        self.org.save()
        self.assertContentMenu(read_url, self.customer_support, [])

    def test_list_and_update(self):
        self.setUpLocations()

        manage_url = reverse("staff.org_list")
        update_url = reverse("staff.org_update", args=[self.org.id])

        self.assertStaffOnly(manage_url)
        self.assertStaffOnly(update_url)

        def assertOrgFilter(query: str, expected_orgs: list):
            response = self.client.get(manage_url + query)
            self.assertIsNotNone(response.headers.get(TEMBA_MENU_SELECTION, None))
            self.assertEqual(expected_orgs, list(response.context["object_list"]))

        assertOrgFilter("", [self.org2, self.org])
        assertOrgFilter("?filter=all", [self.org2, self.org])
        assertOrgFilter("?filter=xxxx", [self.org2, self.org])
        assertOrgFilter("?filter=flagged", [])
        assertOrgFilter("?filter=anon", [])
        assertOrgFilter("?filter=suspended", [])
        assertOrgFilter("?filter=verified", [])

        self.org.flag()

        assertOrgFilter("?filter=flagged", [self.org])

        self.org2.verify()

        assertOrgFilter("?filter=verified", [self.org2])

        # and can go to our org
        response = self.client.get(update_url)
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            [
                "name",
                "features",
                "is_anon",
                "channels_limit",
                "fields_limit",
                "globals_limit",
                "groups_limit",
                "labels_limit",
                "llms_limit",
                "teams_limit",
                "topics_limit",
                "loc",
            ],
            list(response.context["form"].fields.keys()),
        )

        # make some changes to our org
        response = self.client.post(
            update_url,
            {
                "name": "Temba II",
                "features": ["new_orgs"],
                "is_anon": False,
                "channels_limit": 20,
                "fields_limit": 300,
                "globals_limit": "",
                "groups_limit": 400,
                "labels_limit": "",
                "llms_limit": "",
                "teams_limit": "",
                "topics_limit": "",
            },
        )
        self.assertEqual(302, response.status_code)

        self.org.refresh_from_db()
        self.assertEqual("Temba II", self.org.name)
        self.assertEqual(["new_orgs"], self.org.features)
        self.assertEqual(self.org.get_limit(Org.LIMIT_FIELDS), 300)
        self.assertEqual(self.org.get_limit(Org.LIMIT_GLOBALS), 250)  # uses default
        self.assertEqual(self.org.get_limit(Org.LIMIT_GROUPS), 400)
        self.assertEqual(self.org.get_limit(Org.LIMIT_CHANNELS), 20)

        # flag org
        self.client.post(update_url, {"action": "flag"})
        self.org.refresh_from_db()
        self.assertTrue(self.org.is_flagged)

        # unflag org
        self.client.post(update_url, {"action": "unflag"})
        self.org.refresh_from_db()
        self.assertFalse(self.org.is_flagged)

        # suspend org
        self.client.post(update_url, {"action": "suspend"})
        self.org.refresh_from_db()
        self.assertTrue(self.org.is_suspended)

        # unsuspend org
        self.client.post(update_url, {"action": "unsuspend"})
        self.org.refresh_from_db()
        self.assertFalse(self.org.is_suspended)

        # verify
        self.client.post(update_url, {"action": "verify"})
        self.org.refresh_from_db()
        self.assertTrue(self.org.is_verified)

    @mock_mailroom
    def test_service(self, mr_mocks):
        service_url = reverse("staff.org_service")
        inbox_url = reverse("msgs.msg_inbox")

        # without logging in, try to service our main org
        response = self.client.get(service_url, {"other_org": self.org.id, "next": inbox_url})
        self.assertLoginRedirect(response)

        response = self.client.post(service_url, {"other_org": self.org.id})
        self.assertLoginRedirect(response)

        # try logging in with a normal user
        self.login(self.admin)

        # same thing, no permission
        response = self.client.get(service_url, {"other_org": self.org.id, "next": inbox_url})
        self.assertLoginRedirect(response)

        response = self.client.post(service_url, {"other_org": self.org.id})
        self.assertLoginRedirect(response)

        # ok, log in as our cs rep
        self.login(self.customer_support)

        # getting invalid org, has no service form
        response = self.client.get(service_url, {"other_org": 325253256, "next": inbox_url})
        self.assertContains(response, "Invalid org")

        # posting invalid org takes you back out
        response = self.client.post(service_url, {"other_org": 325253256})
        self.assertRedirect(response, reverse("staff.org_list"))

        # then service our org
        response = self.client.get(service_url, {"other_org": self.org.id})
        self.assertContains(response, "You are about to service the workspace, <b>Nyaruka</b>.")

        # requesting a next page has a slightly different message
        response = self.client.get(service_url, {"other_org": self.org.id, "next": inbox_url})
        print(inbox_url)
        self.assertContains(response, "The page you are requesting belongs to a different workspace, <b>Nyaruka</b>.")

        response = self.client.post(service_url, {"other_org": self.org.id})
        self.assertRedirect(response, "/org/start/")
        self.assertEqual(self.org.id, self.client.session["org_id"])

        # specify redirect_url
        response = self.client.post(service_url, {"other_org": self.org.id, "next": "/flow/"})
        self.assertRedirect(response, "/flow/")

        # try to create a new contact (should fail because servicing staff can't POST)
        response = self.client.post(
            reverse("contacts.contact_create"), data={"name": "Ben Haggerty", "phone": "0788123123"}
        )
        self.assertEqual(403, response.status_code)

        # but should be able to export
        response = self.client.post(reverse("contacts.contact_export"))
        self.assertEqual(200, response.status_code)

        response = self.client.post(reverse("tickets.ticket_export"))
        self.assertEqual(200, response.status_code)

        # become super user
        self.customer_support.is_superuser = True
        self.customer_support.save(update_fields=("is_superuser",))

        # now it should work
        response = self.client.post(
            reverse("contacts.contact_create"), data={"name": "Ben Haggerty", "phone": "0788123123"}
        )
        self.assertEqual(200, response.status_code)

        contact = Contact.objects.get(urns__path="+250788123123", org=self.org)
        self.assertEqual(self.customer_support, contact.created_by)
        self.assertEqual(self.org.id, self.client.session["org_id"])

        # stop servicing
        response = self.client.post(service_url, {})
        self.assertRedirect(response, reverse("staff.org_list"))
        self.assertIsNone(self.client.session["org_id"])


class UserCRUDLTest(TembaTest, CRUDLTestMixin):
    def test_list(self):
        list_url = reverse("staff.user_list")

        self.assertStaffOnly(list_url)

        response = self.requestView(list_url, self.customer_support)
        self.assertEqual(8, len(response.context["object_list"]))
        self.assertEqual("/staff/users/all", response.headers[TEMBA_MENU_SELECTION])

        response = self.requestView(list_url + "?filter=beta", self.customer_support)
        self.assertEqual(set(), set(response.context["object_list"]))

        response = self.requestView(list_url + "?filter=staff", self.customer_support)
        self.assertEqual({self.customer_support}, set(response.context["object_list"]))

        response = self.requestView(list_url + "?search=admin@textit.com", self.customer_support)
        self.assertEqual({self.admin}, set(response.context["object_list"]))

        response = self.requestView(list_url + "?search=admin@textit.com", self.customer_support)
        self.assertEqual({self.admin}, set(response.context["object_list"]))

        response = self.requestView(list_url + "?search=Andy", self.customer_support)
        self.assertEqual({self.admin}, set(response.context["object_list"]))

    def test_read(self):
        read_url = reverse("staff.user_read", args=[self.editor.id])

        # this is a customer support only view
        self.assertStaffOnly(read_url)

        # we should have option to unverify
        self.assertContentMenu(read_url, self.customer_support, ["Edit", "Unverify", "Delete"])

        self.editor.set_verified(False)
        Authenticator.objects.create(user_id=self.editor.id, type=Authenticator.Type.TOTP, data={"secret": "sesame"})

        self.assertContentMenu(read_url, self.customer_support, ["Edit", "Verify", "Disable MFA", "Delete"])

    def test_update(self):
        update_url = reverse("staff.user_update", args=[self.editor.id])

        # this is a customer support only view
        self.assertStaffOnly(update_url)

        response = self.requestView(update_url, self.customer_support)
        self.assertEqual(200, response.status_code)

        granters = Group.objects.get(name="Granters")
        betas = Group.objects.get(name="Beta")

        response = self.requestView(
            update_url,
            self.customer_support,
            post_data={
                "email": "eddy@textit.com",
                "first_name": "Edward",
                "last_name": "",
                "groups": [granters.id, betas.id],
            },
        )
        self.assertEqual(302, response.status_code)

        self.editor.refresh_from_db()
        self.assertEqual("eddy@textit.com", self.editor.email)
        self.assertEqual("Edward", self.editor.first_name)
        self.assertEqual("", self.editor.last_name)
        self.assertEqual({granters, betas}, set(self.editor.groups.all()))

        # submit with one less group
        response = self.requestView(
            update_url,
            self.customer_support,
            post_data={
                "email": "eddy@textit.com",
                "new_password": "Asdf1234",
                "first_name": "Edward",
                "last_name": "",
                "groups": [granters.id],
            },
        )
        self.assertEqual(302, response.status_code)

        self.editor.refresh_from_db()
        self.assertEqual("eddy@textit.com", self.editor.email)
        self.assertEqual("Edward", self.editor.first_name)
        self.assertEqual("", self.editor.last_name)
        self.assertEqual({granters}, set(self.editor.groups.all()))

        # unverify user
        self.client.post(update_url, {"action": "unverify"})
        self.editor.refresh_from_db()
        self.assertFalse(self.editor.is_verified())

        # verify user
        self.client.post(update_url, {"action": "verify"})
        self.editor.refresh_from_db()
        self.assertTrue(self.editor.is_verified())

        Authenticator.objects.create(user_id=self.editor.id, type=Authenticator.Type.TOTP, data={"secret": "sesame"})
        self.assertTrue(self.editor.is_mfa_enabled)

        # disable MFA for user
        self.client.post(update_url, {"action": "disable-mfa"})
        self.editor.refresh_from_db()
        self.assertFalse(self.editor.is_mfa_enabled)

    @mock_mailroom
    def test_delete(self, mr_mocks):
        delete_url = reverse("staff.user_delete", args=[self.editor.id])

        # this is a customer support only view
        self.assertStaffOnly(delete_url)

        response = self.requestView(delete_url, self.customer_support)
        self.assertEqual(200, response.status_code)
        self.assertNotContains(response, "Nyaruka")  # editor doesn't own this org

        # make editor the owner of the org
        OrgMembership.objects.filter(org=self.org, role_code=OrgRole.ADMINISTRATOR.code).delete()
        OrgMembership.objects.filter(org=self.org, role_code=OrgRole.AGENT.code).delete()

        response = self.requestView(delete_url, self.customer_support)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Nyaruka")

        response = self.requestView(delete_url, self.customer_support, post_data={})
        self.assertEqual(reverse("staff.user_list"), response["X-Temba-Success"])

        self.editor.refresh_from_db()
        self.assertFalse(self.editor.is_active)

        self.org.refresh_from_db()
        self.assertFalse(self.org.is_active)
