from django.conf import settings
from django.test import override_settings
from django.urls import reverse

from temba.orgs.models import OrgRole
from temba.tests import TembaTest, override_brand


class MiddlewareTest(TembaTest):
    def test_org(self):
        index_url = reverse("public.public_index")

        response = self.client.get(index_url)
        self.assertFalse(response.has_header("X-Temba-Org"))

        # if a user has a single org, that becomes the current org
        self.login(self.admin)

        response = self.client.get(index_url)
        self.assertEqual(str(self.org.id), response["X-Temba-Org"])

        # add them to another org
        self.org2.add_user(self.admin, OrgRole.ADMINISTRATOR)

        # we'll still have the original org
        response = self.client.get(index_url)
        self.assertEqual(str(self.org.id), response["X-Temba-Org"])

        # but when we login again, it'll select the newest org
        self.login(self.admin)
        response = self.client.get(index_url)
        self.assertEqual(str(self.org2.id), response["X-Temba-Org"])

        # org will be read from session if set
        s = self.client.session
        s.update({"org_id": self.org.id})
        s.save()

        response = self.client.get(index_url)
        self.assertEqual(str(self.org.id), response["X-Temba-Org"])

        # org can be sent as a header too and we check it matches
        response = self.client.post(reverse("flows.flow_create"), {}, headers={"X-Temba-Org": str(self.org.id)})
        self.assertEqual(200, response.status_code)

        response = self.client.post(reverse("flows.flow_create"), {}, headers={"X-Temba-Org": str(self.org2.id)})
        self.assertEqual(403, response.status_code)

        self.login(self.customer_support)

        # our staff user doesn't have a default org
        response = self.client.get(index_url)
        self.assertFalse(response.has_header("X-Temba-Org"))

        # but they can specify an org to service as a header
        response = self.client.get(index_url, headers={"X-Temba-Service-Org": str(self.org.id)})
        self.assertEqual(response["X-Temba-Org"], str(self.org.id))

        response = self.client.get(index_url)
        self.assertFalse(response.has_header("X-Temba-Org"))

        self.login(self.editor)

        response = self.client.get(index_url)
        self.assertEqual(response["X-Temba-Org"], str(self.org.id))

        # non-staff can't specify a different org from there own
        response = self.client.get(index_url, headers={"X-Temba-Service-Org": str(self.org2.id)})
        self.assertNotEqual(response["X-Temba-Org"], str(self.org2.id))

    def test_redirect(self):
        self.assertNotRedirect(self.client.get(reverse("public.public_index")), None)

        # now set our brand to redirect
        with override_brand(redirect="/redirect"):
            self.assertRedirect(self.client.get(reverse("public.public_index")), "/redirect")

    def test_language(self):
        def assert_text(text: str):
            self.assertContains(self.client.get(settings.LOGIN_URL, follow=True), text)

        # default is English
        assert_text("continue?")

        # can be overridden in Django settings
        with override_settings(DEFAULT_LANGUAGE="es"):
            assert_text("continuar?")

        # if we have an authenticated user, their setting takes priority
        self.login(self.admin)

        self.admin.language = "fr"
        self.admin.save(update_fields=("language",))

        assert_text("continuer?")
