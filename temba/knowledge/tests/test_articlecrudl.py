from unittest.mock import patch

from django.conf import settings
from django.urls import reverse

from temba.knowledge.models import Article, Knowledge
from temba.orgs.models import Org
from temba.tests import CRUDLTestMixin, TembaTest, cleanup
from temba.utils import json
from temba.utils.s3 import public_file_storage


class ArticleCRUDLTest(TembaTest, CRUDLTestMixin):
    def setUp(self):
        super().setUp()

        self.helpdesk = self.org.knowledge.get(knowledge_type=Knowledge.TYPE_HELPDESK)

    def enable_agents(self, org):
        org.features = [Org.FEATURE_AGENTS]
        org.save(update_fields=("features",))

    def test_list(self):
        list_url = reverse("knowledge.article_list")

        # nobody can access if agents feature not enabled
        response = self.requestView(list_url, self.admin)
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.enable_agents(self.org)

        self.assertRequestDisallowed(list_url, [None, self.agent])

        flows = Article.create(self.helpdesk, self.admin, "Flows")
        Article.create(self.helpdesk, self.admin, "Nodes", parent=flows)

        response = self.requestView(list_url, self.editor)

        self.assertEqual(200, response.status_code)
        self.assertEqual(self.helpdesk, response.context["object"])
        self.assertEqual(["Flows", "Nodes"], [a.title for a in response.context["tree"]])
        self.assertEqual([0, 1], [a.depth for a in response.context["tree"]])
        self.assertContains(response, "Flows")

        self.assertContentMenu(list_url, self.admin, ["New"])

        # 404 if the system source is somehow absent
        self.org.knowledge.filter(knowledge_type=Knowledge.TYPE_HELPDESK).update(is_active=False)
        response = self.requestView(list_url, self.admin)
        self.assertEqual(404, response.status_code)

    def test_read(self):
        article = Article.create(self.helpdesk, self.admin, "Flows", body="# Flows\n\nAre **great**.")
        other_org = Article.create(
            self.org2.knowledge.get(knowledge_type=Knowledge.TYPE_HELPDESK), self.admin2, "Other"
        )

        read_url = reverse("knowledge.article_read", args=[article.uuid])

        # nobody can access if agents feature not enabled
        response = self.requestView(read_url, self.admin)
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.enable_agents(self.org)

        self.assertRequestDisallowed(read_url, [None, self.agent, self.admin2])

        response = self.assertReadFetch(read_url, [self.editor, self.admin], context_object=article)

        self.assertEqual("<h1>Flows</h1>\n<p>Are <strong>great</strong>.</p>", response.context["rendered"])
        self.assertContains(response, "<strong>great</strong>")
        self.assertContains(response, "This article is a draft")

        # a draft offers publishing, a published article offers the reverse
        self.assertContentMenu(read_url, self.admin, ["Edit", "Publish", "Delete"])

        article.publish(self.admin)
        self.assertContentMenu(read_url, self.admin, ["Edit", "Unpublish", "Delete"])

        response = self.requestView(read_url, self.admin)
        self.assertNotContains(response, "This article is a draft")

        # another org's articles aren't ours to read even if we know the uuid
        self.enable_agents(self.org2)
        response = self.requestView(reverse("knowledge.article_read", args=[other_org.uuid]), self.admin)
        self.assertEqual(404, response.status_code)

    def test_create(self):
        create_url = reverse("knowledge.article_create")

        # nobody can access if agents feature not enabled
        response = self.requestView(create_url, self.admin)
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.enable_agents(self.org)

        self.assertRequestDisallowed(create_url, [None, self.agent])

        # a multi-language workspace is asked which language an article is in
        self.org.set_flow_languages(self.admin, ["eng", "spa"])
        self.assertCreateFetch(create_url, [self.editor, self.admin], form_fields=("title", "language"))

        # one with a single language isn't
        self.org.set_flow_languages(self.admin, ["eng"])
        self.assertCreateFetch(create_url, [self.admin], form_fields=("title",))

        self.org.set_flow_languages(self.admin, ["eng", "spa"])

        self.assertCreateSubmit(
            create_url,
            self.admin,
            {"title": "Getting Started", "language": "spa"},
            new_obj_query=Article.objects.filter(title="Getting Started", knowledge=self.helpdesk),
        )

        article = Article.objects.get(title="Getting Started")
        self.assertEqual("getting-started", article.slug)
        self.assertEqual("spa", article.language)
        self.assertEqual(Article.STATUS_DRAFT, article.status)  # new articles are drafts

        # and we're dropped straight into the editor
        response = self.requestView(create_url, self.admin, post_data={"title": "Flows", "language": "eng"})
        self.assertRedirect(
            response, reverse("knowledge.article_update", args=[Article.objects.get(title="Flows").uuid])
        )

        # can't create beyond the limit
        with patch("temba.knowledge.models.Article.MAX_ARTICLES", 2):
            response = self.requestView(create_url, self.admin)
            self.assertContains(response, "You have reached the limit")

            response = self.requestView(create_url, self.admin, post_data={"title": "Nope", "language": "eng"})
            self.assertEqual(200, response.status_code)
            self.assertFalse(Article.objects.filter(title="Nope").exists())

    def test_update(self):
        article = Article.create(self.helpdesk, self.admin, "Flows")

        update_url = reverse("knowledge.article_update", args=[article.uuid])

        # nobody can access if agents feature not enabled
        response = self.requestView(update_url, self.admin)
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.enable_agents(self.org)

        self.assertRequestDisallowed(update_url, [None, self.agent, self.admin2])

        response = self.assertUpdateFetch(
            update_url, [self.editor, self.admin], form_fields=("title", "language", "body")
        )

        # the editor is pointed at this article for uploads and at the shared renderer for previews
        self.assertContains(response, reverse("knowledge.article_upload", args=[article.uuid]))
        self.assertContains(response, reverse("knowledge.article_preview"))

        self.assertUpdateSubmit(
            update_url, self.admin, {"title": "All About Flows", "language": "kin", "body": "# Flows"}
        )

        article.refresh_from_db()
        self.assertEqual("All About Flows", article.title)
        self.assertEqual("# Flows", article.body)
        self.assertEqual("all-about-flows", article.slug)  # the slug follows the title
        self.assertEqual("kin", article.language)
        self.assertEqual(Article.STATUS_DRAFT, article.status)  # saving an edit doesn't publish

        self.assertContentMenu(update_url, self.admin, ["View"])

        # an article keeps the language it was written in as a choice even if the workspace later drops it, so that
        # dropping a language can't make its articles permanently unsaveable
        self.org.set_flow_languages(self.admin, ["eng"])
        Article.objects.filter(id=article.id).update(language="spa")

        response = self.assertUpdateFetch(update_url, [self.admin], form_fields=("title", "language", "body"))
        self.assertEqual([("eng", "English"), ("spa", "Spanish")], response.context["form"].fields["language"].choices)

    def test_publishing(self):
        article = Article.create(self.helpdesk, self.admin, "Flows")

        publish_url = reverse("knowledge.article_publish", args=[article.uuid])
        unpublish_url = reverse("knowledge.article_unpublish", args=[article.uuid])

        # nobody can access if agents feature not enabled
        response = self.requestView(publish_url, self.admin, post_data={})
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.enable_agents(self.org)

        self.assertRequestDisallowed(publish_url, [None, self.agent, self.admin2])

        self.login(self.admin)

        # GET isn't allowed
        self.assertEqual(405, self.client.get(publish_url).status_code)

        response = self.client.post(publish_url)
        self.assertRedirect(response, reverse("knowledge.article_read", args=[article.uuid]))

        article.refresh_from_db()
        self.assertEqual(Article.STATUS_PUBLISHED, article.status)
        self.assertIsNotNone(article.published_on)

        self.assertEqual(405, self.client.get(unpublish_url).status_code)

        response = self.client.post(unpublish_url)
        self.assertRedirect(response, reverse("knowledge.article_read", args=[article.uuid]))

        article.refresh_from_db()
        self.assertEqual(Article.STATUS_DRAFT, article.status)
        self.assertIsNone(article.published_on)

    def test_sort(self):
        flows = Article.create(self.helpdesk, self.admin, "Flows")
        nodes = Article.create(self.helpdesk, self.admin, "Nodes")

        sort_url = reverse("knowledge.article_sort")

        # nobody can access if agents feature not enabled
        response = self.requestView(sort_url, self.admin, post_data={})
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.enable_agents(self.org)

        self.assertRequestDisallowed(sort_url, [None, self.agent])

        self.login(self.admin)

        # GET isn't allowed
        self.assertEqual(405, self.client.get(sort_url).status_code)

        response = self.client.post(
            sort_url,
            json.dumps(
                [
                    {"uuid": str(nodes.uuid), "parent": None, "sort_order": 0},
                    {"uuid": str(flows.uuid), "parent": str(nodes.uuid), "sort_order": 0},
                ]
            ),
            content_type="application/json",
        )
        self.assertEqual({"status": "ok"}, response.json())

        flows.refresh_from_db()
        self.assertEqual(nodes, flows.parent)

        # a malformed payload is rejected without touching anything, as is one whose sort orders aren't finite or
        # which names more articles than a helpdesk can hold
        for payload in (
            '{"nope": 1}',
            "[{}]",
            '[{"uuid": "x", "parent": null, "sort_order": "y"}]',
            "not json",
            '[{"uuid": "x", "parent": null, "sort_order": Infinity}]',
        ):
            response = self.client.post(sort_url, payload, content_type="application/json")
            self.assertEqual(400, response.status_code)
            self.assertEqual({"error": "Invalid ordering."}, response.json())

        with patch("temba.knowledge.models.Article.MAX_ARTICLES", 1):
            response = self.client.post(
                sort_url,
                json.dumps([{"uuid": str(u), "parent": None, "sort_order": 0} for u in (flows.uuid, nodes.uuid)]),
                content_type="application/json",
            )
            self.assertEqual(400, response.status_code)
            self.assertEqual({"error": "Invalid ordering."}, response.json())

        # as is a tree the model won't accept - the client is never trusted
        response = self.client.post(
            sort_url,
            json.dumps([{"uuid": str(nodes.uuid), "parent": str(flows.uuid), "sort_order": 0}]),
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual({"error": "articles can't be their own ancestor"}, response.json())

        # a sort order too big for the column is clamped rather than handed to the database
        response = self.client.post(
            sort_url,
            json.dumps([{"uuid": str(flows.uuid), "parent": None, "sort_order": 2**40}]),
            content_type="application/json",
        )
        self.assertEqual({"status": "ok"}, response.json())

        flows.refresh_from_db()
        self.assertEqual(Article.MAX_ARTICLES, flows.sort_order)

    def test_preview(self):
        preview_url = reverse("knowledge.article_preview")

        # nobody can access if agents feature not enabled
        response = self.requestView(preview_url, self.admin, post_data={})
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.enable_agents(self.org)

        self.assertRequestDisallowed(preview_url, [None, self.agent])

        self.login(self.admin)

        # GET isn't allowed
        self.assertEqual(405, self.client.get(preview_url).status_code)

        # renders with the same sanitizing renderer as the read page
        response = self.client.post(preview_url, {"body": "# Hi\n\n<script>alert(1)</script>"})
        self.assertEqual({"html": "<h1>Hi</h1>\n"}, response.json())

        response = self.client.post(preview_url, {})
        self.assertEqual({"html": ""}, response.json())

    @cleanup(s3=True)
    def test_upload(self):
        article = Article.create(self.helpdesk, self.admin, "Flows")

        upload_url = reverse("knowledge.article_upload", args=[article.uuid])

        # nobody can access if agents feature not enabled
        response = self.requestView(upload_url, self.admin, post_data={})
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.enable_agents(self.org)

        self.assertRequestDisallowed(upload_url, [None, self.agent, self.admin2])

        self.login(self.admin)

        # GET isn't allowed
        self.assertEqual(405, self.client.get(upload_url).status_code)

        # can't upload a file type we don't support (sniffed, not the browser supplied type)
        response = self.client.post(
            upload_url, {"file": self.upload(f"{settings.MEDIA_ROOT}/test_media/simple.pdf", "image/png")}
        )
        self.assertEqual({"error": "Unsupported file type"}, response.json())

        # can't upload a file that's too big
        with patch("temba.knowledge.models.ArticleImage.MAX_UPLOAD_SIZE", 10):
            response = self.client.post(
                upload_url, {"file": self.upload(f"{settings.MEDIA_ROOT}/test_media/klab.png", "image/png")}
            )
            self.assertEqual({"error": "Limit for file uploads is 9.5367431640625e-06 MB"}, response.json())

        # can't exceed the per article limit
        with patch("temba.knowledge.models.ArticleImage.MAX_IMAGES", 0):
            response = self.client.post(
                upload_url, {"file": self.upload(f"{settings.MEDIA_ROOT}/test_media/klab.png", "image/png")}
            )
            self.assertEqual({"error": "Limit of 0 images reached."}, response.json())

        response = self.client.post(
            upload_url, {"file": self.upload(f"{settings.MEDIA_ROOT}/test_media/klab.png", "image/png")}
        )

        image = article.images.get()
        self.assertEqual({"uuid": str(image.uuid), "name": "klab.png", "url": image.url}, response.json())
        self.assertEqual("image/png", image.content_type)
        self.assertTrue(public_file_storage.exists(image.path))

    @cleanup(s3=True)
    def test_delete(self):
        parent = Article.create(self.helpdesk, self.admin, "Flows")
        child = Article.create(self.helpdesk, self.admin, "Nodes", parent=parent)

        delete_url = reverse("knowledge.article_delete", args=[parent.uuid])

        # nobody can access if agents feature not enabled
        response = self.requestView(delete_url, self.admin)
        self.assertRedirect(response, reverse("orgs.org_workspace"))

        self.enable_agents(self.org)

        self.assertRequestDisallowed(delete_url, [None, self.agent, self.admin2])

        response = self.assertDeleteFetch(delete_url, [self.editor, self.admin])
        self.assertContains(response, "You are about to delete")

        response = self.assertDeleteSubmit(delete_url, self.admin, object_deactivated=parent, success_status=302)
        self.assertEqual(reverse("knowledge.article_list"), response.url)

        # the child is reparented rather than orphaned
        child.refresh_from_db()
        self.assertIsNone(child.parent)
        self.assertTrue(child.is_active)
