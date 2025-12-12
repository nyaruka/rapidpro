from django.urls import reverse

from temba.orgs.models import OrgRole
from temba.tests import TembaTest


class OrgPermsMixinTest(TembaTest):
    def test_has_permission(self):
        create_url = reverse("tickets.topic_create")

        # no anon access
        self.assertLoginRedirect(self.client.get(create_url))

        # no agent role access to this specific view
        self.login(self.agent)
        self.assertLoginRedirect(self.client.get(create_url))

        # editor role does have access tho
        self.login(self.editor)
        self.assertEqual(200, self.client.get(create_url).status_code)

        # staff can't access without org
        self.login(self.customer_support)
        self.assertLoginRedirect(self.client.get(create_url))

        self.login(self.customer_support, choose_org=self.org)
        self.assertEqual(200, self.client.get(create_url).status_code)

        # staff still can't POST
        self.assertEqual(403, self.client.post(create_url, {"name": "Sales"}).status_code)

        # but superuser can
        self.customer_support.is_superuser = True
        self.customer_support.save(update_fields=("is_superuser",))

        self.assertEqual(200, self.client.get(create_url).status_code)
        self.assertRedirect(self.client.post(create_url, {"name": "Sales"}), "hide")

        # however if a staff user also belongs to an org, they aren't limited to GETs
        self.admin.is_staff = True
        self.admin.save(update_fields=("is_staff",))

        self.assertEqual(200, self.client.get(create_url).status_code)
        self.assertRedirect(self.client.post(create_url, {"name": "Support"}), "hide")

    def test_obj_perms_mixin(self):
        contact1 = self.create_contact("Bob", phone="+18001234567", org=self.org)
        contact2 = self.create_contact("Zob", phone="+18001234567", org=self.org2)
        self.org2.add_user(self.admin, OrgRole.ADMINISTRATOR)

        org1_read_url = reverse("contacts.contact_read", args=[contact1.uuid])
        org1_update_url = reverse("contacts.contact_update", args=[contact1.uuid])
        org2_read_url = reverse("contacts.contact_read", args=[contact2.uuid])
        org2_update_url = reverse("contacts.contact_update", args=[contact2.uuid])

        # no anon access to anything
        self.assertLoginRedirect(self.client.get(org1_read_url))
        self.assertLoginRedirect(self.client.get(org1_update_url))
        self.assertLoginRedirect(self.client.get(org2_read_url))
        self.assertLoginRedirect(self.client.get(org2_update_url))

        # no agent role access to these views
        self.login(self.agent)
        self.assertLoginRedirect(self.client.get(org1_read_url))
        self.assertLoginRedirect(self.client.get(org1_update_url))
        self.assertLoginRedirect(self.client.get(org2_read_url))
        self.assertLoginRedirect(self.client.get(org2_update_url))

        # editor does have access tho for contacts in their org
        self.login(self.editor)
        self.assertEqual(200, self.client.get(org1_read_url).status_code)
        self.assertEqual(200, self.client.get(org1_update_url).status_code)
        self.assertEqual(404, self.client.get(org2_read_url).status_code)
        self.assertEqual(404, self.client.get(org2_update_url).status_code)

        # admin belongs to both orgs
        self.login(self.admin, choose_org=self.org)
        self.assertEqual(200, self.client.get(org1_read_url).status_code)
        self.assertEqual(200, self.client.get(org1_update_url).status_code)
        self.assertRedirect(self.client.get(org2_read_url), reverse("orgs.org_switch"))  # read views redirect
        self.assertEqual(404, self.client.get(org2_update_url).status_code)

        # staff can't access without org
        self.login(self.customer_support)
        self.assertRedirect(self.client.get(org1_read_url), "/staff/org/service/")

        self.login(self.customer_support, choose_org=self.org)
        self.assertEqual(200, self.client.get(org1_read_url).status_code)
        self.assertRedirect(self.client.get(org2_read_url), "/staff/org/service/")  # wrong org

        # staff still can't POST
        self.assertEqual(403, self.client.post(org1_update_url, {"name": "Bob"}).status_code)
        self.assertEqual(404, self.client.get(org2_update_url).status_code)
