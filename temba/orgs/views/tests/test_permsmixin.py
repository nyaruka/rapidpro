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

        contact1_url = reverse("contacts.contact_update", args=[contact1.id])
        contact2_url = reverse("contacts.contact_update", args=[contact2.id])

        # no anon access
        self.assertLoginRedirect(self.client.get(contact1_url))
        self.assertLoginRedirect(self.client.get(contact2_url))

        # no agent role access to this specific view
        self.login(self.agent)
        self.assertLoginRedirect(self.client.get(contact1_url))
        self.assertLoginRedirect(self.client.get(contact2_url))

        # editor does have access tho.. when the URL is for a contact in their org
        self.login(self.editor)
        self.assertEqual(200, self.client.get(contact1_url).status_code)
        self.assertLoginRedirect(self.client.get(contact2_url))

        # admin belongs to both orgs
        self.login(self.admin, choose_org=self.org)
        self.assertEqual(200, self.client.get(contact1_url).status_code)
        self.assertRedirect(self.client.get(contact2_url), reverse("orgs.org_choose"))

        # staff can't access without org
        self.login(self.customer_support)
        self.assertRedirect(self.client.get(contact1_url), "/staff/org/service/")

        self.login(self.customer_support, choose_org=self.org)
        self.assertEqual(200, self.client.get(contact1_url).status_code)
        self.assertRedirect(self.client.get(contact2_url), "/staff/org/service/")  # wrong org

        # staff still can't POST
        self.assertEqual(403, self.client.post(contact1_url, {"name": "Bob"}).status_code)
        self.assertRedirect(self.client.get(contact2_url), "/staff/org/service/")
