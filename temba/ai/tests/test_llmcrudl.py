from django.test import override_settings
from django.urls import reverse

from temba.ai.models import LLM
from temba.ai.types.anthropic.type import AnthropicType
from temba.ai.types.openai.type import OpenAIType
from temba.tests import CRUDLTestMixin, TembaTest, mock_mailroom
from temba.utils.views.mixins import TEMBA_MENU_SELECTION


class LLMCRUDLTest(TembaTest, CRUDLTestMixin):
    def setUp(self):
        super().setUp()

        self.openai = LLM.create(self.org, self.admin, OpenAIType, "GPT-4", {})
        self.anthropic = LLM.create(self.org, self.admin, AnthropicType, "Claude", {})
        LLM.create(self.org2, self.admin2, OpenAIType, "Other Org", {})

    def test_list(self):
        list_url = reverse("ai.llm_list")

        self.assertRequestDisallowed(list_url, [None, self.agent])

        response = self.assertListFetch(
            list_url, [self.editor, self.admin], context_objects=[self.anthropic, self.openai]
        )
        self.assertEqual("settings/ai", response.headers[TEMBA_MENU_SELECTION])
        self.assertContentMenu(list_url, self.admin, ["New"])
        self.assertContentMenu(list_url, self.editor, [])

        with override_settings(ORG_LIMIT_DEFAULTS={"llms": 2}):
            response = self.assertListFetch(list_url, [self.editor, self.admin], context_object_count=2)
            self.assertContains(response, "You have reached the per-workspace limit")
            self.assertContentMenu(list_url, self.admin, [])

    def test_update(self):
        update_url = reverse("ai.llm_update", args=[self.openai.uuid])

        self.assertRequestDisallowed(update_url, [None, self.agent, self.editor, self.admin2])

        self.assertUpdateFetch(update_url, [self.admin], form_fields={"name": "GPT-4"})

        # names must be unique (case-insensitive)
        self.assertUpdateSubmit(
            update_url,
            self.admin,
            {"name": "claude"},
            form_errors={"name": "Must be unique."},
            object_unchanged=self.openai,
        )

        self.assertUpdateSubmit(update_url, self.admin, {"name": "GPT-4-Turbo"}, success_status=302)

        self.openai.refresh_from_db()
        self.assertEqual(self.openai.name, "GPT-4-Turbo")

    @mock_mailroom
    def test_translate(self, mr_mocks):
        translate_url = reverse("ai.llm_translate", args=[self.openai.uuid])

        self.assertRequestDisallowed(translate_url, [None, self.agent])

        mr_mocks.llm_translate("Hola")

        self.login(self.editor)
        response = self.client.post(
            translate_url, {"text": "Hello", "lang": {"from": "eng", "to": "spa"}}, content_type="application/json"
        )
        self.assertEqual(response.json(), {"result": "Hola"})

    def test_delete(self):
        list_url = reverse("ai.llm_list")
        delete_url = reverse("ai.llm_delete", args=[self.anthropic.uuid])

        self.flow = self.create_flow("Color Flow")
        self.flow.llm_dependencies.add(self.openai)

        self.assertRequestDisallowed(delete_url, [None, self.editor, self.agent, self.admin2])

        # fetch delete modal
        response = self.assertDeleteFetch(delete_url, [self.admin])
        self.assertContains(response, "You are about to delete")

        response = self.assertDeleteSubmit(
            delete_url, self.admin, object_deactivated=self.anthropic, success_status=200
        )
        self.assertEqual(list_url, response["X-Temba-Success"])

        # should see warning if model is being used
        delete_url = reverse("ai.llm_delete", args=[self.openai.uuid])
        self.assertFalse(self.flow.has_issues)

        response = self.assertDeleteFetch(delete_url, [self.admin])
        self.assertContains(response, "is used by the following items but can still be deleted:")
        self.assertContains(response, "Color Flow")

        response = self.assertDeleteSubmit(delete_url, self.admin, object_deactivated=self.openai, success_status=200)
        self.assertEqual(list_url, response["X-Temba-Success"])

        self.flow.refresh_from_db()
        self.assertTrue(self.flow.has_issues)
        self.assertNotIn(self.openai, self.flow.llm_dependencies.all())
