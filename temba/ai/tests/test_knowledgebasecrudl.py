from django.urls import reverse

from temba.ai.models import KnowledgeBase
from temba.orgs.models import Org
from temba.tests import CRUDLTestMixin, TembaTest
from temba.utils.views.mixins import TEMBA_MENU_SELECTION


class KnowledgeBaseCRUDLTest(TembaTest, CRUDLTestMixin):
    def setUp(self):
        super().setUp()

        # knowledge base views require the agents feature
        self.org.features = [Org.FEATURE_AGENTS]
        self.org.save(update_fields=("features",))
        self.org2.features = [Org.FEATURE_AGENTS]
        self.org2.save(update_fields=("features",))

        self.kb1 = KnowledgeBase.create_website(self.org, self.admin, "Acme Help", "https://help.acme.com/")
        self.kb2 = KnowledgeBase.create_website(self.org, self.admin, "Acme Docs", "https://docs.acme.com/")
        KnowledgeBase.create_website(self.org2, self.admin2, "Other Org", "https://other.com/")

    def test_feature_required(self):
        # without the agents feature, users are redirected to the workspace page
        self.org.features = []
        self.org.save(update_fields=("features",))

        self.login(self.admin)

        self.assertRedirect(self.client.get(reverse("ai.knowledgebase_list")), reverse("orgs.org_workspace"))
        self.assertRedirect(self.client.get(reverse("ai.knowledgebase_create")), reverse("orgs.org_workspace"))
        self.assertRedirect(
            self.client.get(reverse("ai.knowledgebase_read", args=[self.kb1.uuid])), reverse("orgs.org_workspace")
        )
        self.assertRedirect(
            self.client.get(reverse("ai.knowledgebase_delete", args=[self.kb1.uuid])), reverse("orgs.org_workspace")
        )

    def test_list(self):
        list_url = reverse("ai.knowledgebase_list")

        self.assertRequestDisallowed(list_url, [None, self.agent])

        response = self.assertListFetch(list_url, [self.editor, self.admin], context_objects=[self.kb2, self.kb1])
        self.assertEqual("/ai/knowledge", response.headers[TEMBA_MENU_SELECTION])
        self.assertContentMenu(list_url, self.admin, ["New"])

    def test_create(self):
        create_url = reverse("ai.knowledgebase_create")

        self.assertRequestDisallowed(create_url, [None, self.agent])
        self.assertCreateFetch(create_url, [self.editor, self.admin], form_fields=("name", "kb_type", "url"))

        # try to create with empty fields
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {},
            form_errors={"name": "This field is required.", "kb_type": "This field is required."},
        )

        # URL is required for website knowledge bases
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "Acme Support", "kb_type": "W"},
            form_errors={"url": "This field is required."},
        )

        # try to use an existing name
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "acme help", "kb_type": "W", "url": "https://support.acme.com/"},
            form_errors={"name": "Must be unique."},
        )

        response = self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "Acme Support", "kb_type": "W", "url": "https://support.acme.com/"},
            new_obj_query=KnowledgeBase.objects.filter(
                name="Acme Support",
                url="https://support.acme.com/",
                kb_type=KnowledgeBase.TYPE_WEBSITE,
                status=KnowledgeBase.STATUS_PENDING,
                org=self.org,
            ),
        )

        # should redirect to the new knowledge base
        kb = KnowledgeBase.objects.get(name="Acme Support")
        self.assertEqual(reverse("ai.knowledgebase_read", args=[kb.uuid]), response.url)

        # documents and FAQ knowledge bases don't need a URL - even if one is provided it's ignored - and
        # start out complete since there's nothing to process yet
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "Manuals", "kb_type": "D", "url": "https://support.acme.com/"},
            new_obj_query=KnowledgeBase.objects.filter(
                name="Manuals", kb_type=KnowledgeBase.TYPE_DOCUMENTS, url=None, status=KnowledgeBase.STATUS_COMPLETE
            ),
        )
        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"name": "Common Questions", "kb_type": "F"},
            new_obj_query=KnowledgeBase.objects.filter(
                name="Common Questions", kb_type=KnowledgeBase.TYPE_FAQ, url=None, status=KnowledgeBase.STATUS_COMPLETE
            ),
        )

    def test_read(self):
        read_url = reverse("ai.knowledgebase_read", args=[self.kb1.uuid])

        self.kb1.articles.create(url="https://help.acme.com/articles/one", title="Article One", content="stuff")

        self.assertRequestDisallowed(read_url, [None, self.agent, self.admin2])

        response = self.assertReadFetch(read_url, [self.editor, self.admin], context_object=self.kb1)
        self.assertContains(response, "Article One")
        self.assertContentMenu(read_url, self.admin, ["Delete"])

        # documents and FAQ knowledge bases have their own read pages
        docs = KnowledgeBase.create_documents(self.org, self.admin, "Manuals")
        faq = KnowledgeBase.create_faq(self.org, self.admin, "Common Questions")
        faq.articles.create(title="How do I reset my password?", content="Click forgot password.")

        response = self.assertReadFetch(
            reverse("ai.knowledgebase_read", args=[docs.uuid]), [self.admin], context_object=docs
        )
        self.assertContains(response, "No documents uploaded yet")

        response = self.assertReadFetch(
            reverse("ai.knowledgebase_read", args=[faq.uuid]), [self.admin], context_object=faq
        )
        self.assertContains(response, "How do I reset my password?")

    def test_delete(self):
        delete_url = reverse("ai.knowledgebase_delete", args=[self.kb1.uuid])

        self.assertRequestDisallowed(delete_url, [None, self.agent, self.admin2])

        self.assertDeleteFetch(delete_url, [self.editor, self.admin])
        self.assertDeleteSubmit(delete_url, self.admin, object_deactivated=self.kb1)
