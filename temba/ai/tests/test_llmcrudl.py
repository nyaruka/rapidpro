from django.urls import reverse

from temba.ai.models import LLM
from temba.ai.types.openai.type import OpenAIType
from temba.tests import CRUDLTestMixin, TembaTest
from temba.utils.views.mixins import TEMBA_MENU_SELECTION


class LLMCRUDLTest(TembaTest, CRUDLTestMixin):
    def setUp(self):
        super().setUp()

        self.basic = LLM.create(self.org, self.admin, OpenAIType.slug, "Basic", "api_key", "gpt-turbo-3.5")
        self.advanced = LLM.create(self.org, self.admin, OpenAIType.slug, "Advanced", "api_key", "gpt-4o")

        self.flow = self.create_flow("Color Flow")
        self.flow.llm_dependencies.add(self.basic)

    def test_list(self):

        self.login(self.admin)
        list_url = reverse("ai.llm_list")
        response = self.assertListFetch(list_url, [self.admin])
        self.assertEqual("settings/ai", response.headers[TEMBA_MENU_SELECTION])

    def test_delete(self):
        list_url = reverse("ai.llm_list")
        delete_url = reverse("ai.llm_delete", args=[self.advanced.uuid])
        self.assertRequestDisallowed(delete_url, [None, self.editor, self.agent, self.admin2])

        # fetch delete modal
        response = self.assertDeleteFetch(delete_url, [self.admin])
        self.assertContains(response, "You are about to delete")

        response = self.assertDeleteSubmit(delete_url, self.admin, object_deactivated=self.advanced, success_status=200)
        self.assertEqual(list_url, response["X-Temba-Success"])

        # should see warning if model is being used
        delete_url = reverse("ai.llm_delete", args=[self.basic.uuid])
        self.assertFalse(self.flow.has_issues)

        response = self.assertDeleteFetch(delete_url, [self.admin])
        self.assertContains(response, "is used by the following items but can still be deleted:")
        self.assertContains(response, "Color Flow")

        response = self.assertDeleteSubmit(delete_url, self.admin, object_deactivated=self.basic, success_status=200)
        self.assertEqual(list_url, response["X-Temba-Success"])

        self.flow.refresh_from_db()
        self.assertTrue(self.flow.has_issues)
        self.assertNotIn(self.basic, self.flow.llm_dependencies.all())
