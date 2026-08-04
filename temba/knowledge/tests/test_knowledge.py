from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test.utils import override_settings

from temba.knowledge.models import (
    Article,
    ArticleImage,
    Knowledge,
    KnowledgeChunk,
    KnowledgeItem,
    get_article_image_path,
)
from temba.tests import TembaTest, cleanup
from temba.utils.s3 import public_file_storage
from temba.utils.uuid import uuid4


class KnowledgeTest(TembaTest):
    def create_chunk(self, knowledge, item_key, text: str):
        return KnowledgeChunk.objects.create(
            knowledge=knowledge, item_key=item_key, item_name="Test", text=text, embedding=[0.0] * 384
        )

    def create_article(self, knowledge, title: str, *, parent=None, status=Article.STATUS_DRAFT):
        return Article.objects.create(
            knowledge=knowledge,
            parent=parent,
            title=title,
            slug=Article.get_unique_slug(knowledge, title),
            status=status,
            created_by=self.admin,
            modified_by=self.admin,
        )

    def test_create_system(self):
        # both orgs got their system sources from Org.initialize()
        shortcuts = self.org.knowledge.get(knowledge_type=Knowledge.TYPE_SHORTCUTS)
        helpdesk = self.org.knowledge.get(knowledge_type=Knowledge.TYPE_HELPDESK)

        self.assertEqual("Shortcuts", shortcuts.name)
        self.assertTrue(shortcuts.is_system)
        self.assertEqual("Helpdesk", helpdesk.name)
        self.assertTrue(helpdesk.is_system)
        self.assertEqual(2, self.org2.knowledge.filter(is_system=True).count())

        # can't create them again
        with self.assertRaises(AssertionError):
            Knowledge.create_system(self.org)

    def test_create_website(self):
        website = Knowledge.create_website(self.org, self.admin, "Nyaruka", "https://nyaruka.com")

        self.assertEqual("Nyaruka", website.name)
        self.assertEqual(Knowledge.TYPE_WEBSITE, website.knowledge_type)
        self.assertEqual("https://nyaruka.com", website.url)
        self.assertEqual(
            {"url": "https://nyaruka.com", "max_depth": 3, "max_pages": 500, "refresh": "weekly"}, website.config
        )
        self.assertEqual(Knowledge.STATUS_PENDING, website.status)
        self.assertFalse(website.is_system)

        # explicit settings are used as given
        custom = Knowledge.create_website(
            self.org, self.admin, "Custom", "https://example.com", max_depth=2, max_pages=100, refresh="daily"
        )
        self.assertEqual(
            {"url": "https://example.com", "max_depth": 2, "max_pages": 100, "refresh": "daily"}, custom.config
        )

        # try to create with an invalid name
        with self.assertRaises(AssertionError):
            Knowledge.create_website(self.org, self.admin, '"Nope"', "https://nyaruka.com")

        # try to create with a name that's taken
        with self.assertRaises(AssertionError):
            Knowledge.create_website(self.org, self.admin, "nyaruka", "https://nyaruka.com")

    def test_create_documents(self):
        docs = Knowledge.create_documents(self.org, self.admin, "Guides")

        self.assertEqual("Guides", docs.name)
        self.assertEqual(Knowledge.TYPE_DOCUMENTS, docs.knowledge_type)
        self.assertEqual({}, docs.config)
        self.assertIsNone(docs.url)
        self.assertEqual(Knowledge.STATUS_READY, docs.status)  # nothing to index yet

        with self.assertRaises(AssertionError):
            Knowledge.create_documents(self.org, self.admin, '"Nope"')
        with self.assertRaises(AssertionError):
            Knowledge.create_documents(self.org, self.admin, "guides")

    def test_unique_names(self):
        Knowledge.create_documents(self.org, self.admin, "Guides")

        with self.assertRaises(IntegrityError):
            self.org.knowledge.create(
                name="GUIDES",
                knowledge_type=Knowledge.TYPE_DOCUMENTS,
                created_by=self.admin,
                modified_by=self.admin,
            )

    @override_settings(ORG_LIMIT_DEFAULTS={"knowledge": 2})
    def test_limits(self):
        # neither system row counts against the limit
        self.assertFalse(Knowledge.is_limit_reached(self.org))

        Knowledge.create_documents(self.org, self.admin, "Guides")
        self.assertFalse(Knowledge.is_limit_reached(self.org))

        Knowledge.create_website(self.org, self.admin, "Nyaruka", "https://nyaruka.com")
        self.assertTrue(Knowledge.is_limit_reached(self.org))
        self.assertFalse(Knowledge.is_limit_reached(self.org2))

    def test_mark_pending(self):
        docs = Knowledge.create_documents(self.org, self.admin, "Guides")
        docs.status = Knowledge.STATUS_FAILED
        docs.error = "boom"
        docs.save(update_fields=("status", "error"))

        docs.mark_pending()

        docs.refresh_from_db()
        self.assertEqual(Knowledge.STATUS_PENDING, docs.status)
        self.assertIsNone(docs.error)

    @cleanup(s3=True)
    def test_release(self):
        docs = Knowledge.create_documents(self.org, self.admin, "Guides")
        item = KnowledgeItem.from_upload(
            docs, self.admin, SimpleUploadedFile("guide.txt", b"hello", content_type="text/plain")
        )
        self.create_chunk(docs, item.uuid, "hello")
        docs.num_items = 1
        docs.num_chunks = 1
        docs.save(update_fields=("num_items", "num_chunks"))

        # can't release either system source
        for kb_type in Knowledge.SYSTEM_TYPES:
            with self.assertRaises(AssertionError):
                self.org.knowledge.get(knowledge_type=kb_type).release(self.admin)

        docs.release(self.admin)

        docs.refresh_from_db()
        self.assertFalse(docs.is_active)
        self.assertTrue(docs.name.startswith("deleted-"))
        self.assertEqual(0, docs.num_items)
        self.assertEqual(0, docs.num_chunks)
        self.assertEqual(0, docs.items.count())
        self.assertEqual(0, docs.chunks.count())
        self.assertFalse(default_storage.exists(item.path))

    @cleanup(s3=True)
    def test_delete(self):
        # deleting purges articles and their images - use the system helpdesk row since that's where articles live
        helpdesk = self.org.knowledge.get(knowledge_type=Knowledge.TYPE_HELPDESK)
        parent = self.create_article(helpdesk, "Flows", status=Article.STATUS_PUBLISHED)
        child = self.create_article(helpdesk, "Nodes", parent=parent)
        self.create_chunk(helpdesk, parent.uuid, "flows are...")

        image_path = public_file_storage.save(
            get_article_image_path(parent, uuid4(), "image/png"), SimpleUploadedFile("shot1.png", b"png")
        )
        ArticleImage.objects.create(
            article=parent,
            name="shot1.png",
            path=image_path,
            content_type="image/png",
            size=3,
            created_by=self.admin,
        )

        helpdesk.delete()

        self.assertFalse(Knowledge.objects.filter(id=helpdesk.id).exists())
        self.assertFalse(Article.objects.filter(id__in=(parent.id, child.id)).exists())
        self.assertEqual(0, ArticleImage.objects.count())
        self.assertEqual(0, KnowledgeChunk.objects.count())
        self.assertFalse(public_file_storage.exists(image_path))


class KnowledgeItemTest(TembaTest):
    def create_chunk(self, knowledge, item_key, text: str):
        return KnowledgeChunk.objects.create(
            knowledge=knowledge, item_key=item_key, item_name="Test", text=text, embedding=[0.0] * 384
        )

    def test_clean_name(self):
        self.assertEqual("guide.pdf", KnowledgeItem.clean_name("guide.pdf"))
        self.assertEqual("guide (1) [final].pdf", KnowledgeItem.clean_name("guide (1) [final].pdf"))
        self.assertEqual("etcpasswd", KnowledgeItem.clean_name("/etc/passwd"))
        self.assertEqual("file.pdf", KnowledgeItem.clean_name("!!!.pdf"))
        self.assertEqual("x" * 200 + ".pdf", KnowledgeItem.clean_name("x" * 300 + ".pdf"))

    def test_is_allowed_type(self):
        self.assertTrue(KnowledgeItem.is_allowed_type("application/pdf"))
        self.assertTrue(KnowledgeItem.is_allowed_type("text/plain"))
        self.assertFalse(KnowledgeItem.is_allowed_type("image/png"))

    @cleanup(s3=True)
    def test_from_upload(self):
        docs = Knowledge.create_documents(self.org, self.admin, "Guides")
        self.assertEqual(Knowledge.STATUS_READY, docs.status)

        item = KnowledgeItem.from_upload(
            docs, self.admin, SimpleUploadedFile("A Guide!.txt", b"hello world", content_type="text/plain")
        )

        self.assertEqual(docs, item.knowledge)
        self.assertEqual("A Guide.txt", item.name)
        self.assertIsNone(item.url)
        self.assertEqual(f"orgs/{self.org.id}/knowledge/{docs.uuid}/{item.uuid}.txt", item.path)
        self.assertEqual("text/plain", item.content_type)
        self.assertEqual(11, item.size)
        self.assertEqual(KnowledgeItem.STATUS_PENDING, item.status)
        self.assertEqual(self.admin, item.created_by)
        self.assertEqual(self.org, item.org)
        self.assertTrue(default_storage.exists(item.path))

        # the parent source now needs reindexing
        docs.refresh_from_db()
        self.assertEqual(Knowledge.STATUS_PENDING, docs.status)

    @cleanup(s3=True)
    def test_delete(self):
        docs = Knowledge.create_documents(self.org, self.admin, "Guides")
        item1 = KnowledgeItem.from_upload(
            docs, self.admin, SimpleUploadedFile("one.txt", b"one", content_type="text/plain")
        )
        item2 = KnowledgeItem.from_upload(
            docs, self.admin, SimpleUploadedFile("two.txt", b"two", content_type="text/plain")
        )
        self.create_chunk(docs, item1.uuid, "one")
        chunk2 = self.create_chunk(docs, item2.uuid, "two")

        docs.status = Knowledge.STATUS_READY
        docs.save(update_fields=("status",))

        item1_path = item1.path
        item1.delete()

        # only item1's chunks are gone and the source is pending again
        self.assertFalse(KnowledgeItem.objects.filter(id=item1.id).exists())
        self.assertEqual([chunk2], list(docs.chunks.all()))
        self.assertFalse(default_storage.exists(item1_path))
        self.assertTrue(default_storage.exists(item2.path))
        docs.refresh_from_db()
        self.assertEqual(Knowledge.STATUS_PENDING, docs.status)

        # a crawled page row has no storage object - deleting it is a no-op on storage
        website = Knowledge.create_website(self.org, self.admin, "Nyaruka", "https://nyaruka.com")
        page = KnowledgeItem.objects.create(
            knowledge=website, name="Home", url="https://nyaruka.com/", content_type="text/html", size=1024
        )
        page.delete()
        self.assertFalse(KnowledgeItem.objects.filter(id=page.id).exists())

    def test_unique_urls(self):
        website = Knowledge.create_website(self.org, self.admin, "Nyaruka", "https://nyaruka.com")
        KnowledgeItem.objects.create(
            knowledge=website, name="Home", url="https://nyaruka.com/", content_type="text/html", size=1024
        )

        # same url within the source collides
        with self.assertRaises(IntegrityError):
            KnowledgeItem.objects.create(
                knowledge=website, name="Home Again", url="https://nyaruka.com/", content_type="text/html", size=1024
            )

    def test_null_urls_can_coexist(self):
        # the subtle side of unique_knowledge_item_urls: NULLs are distinct, so documents are exempt
        docs = Knowledge.create_documents(self.org, self.admin, "Guides")
        KnowledgeItem.objects.create(
            knowledge=docs, name="one.txt", url=None, path="a/b/one.txt", content_type="text/plain", size=3
        )
        KnowledgeItem.objects.create(
            knowledge=docs, name="two.txt", url=None, path="a/b/two.txt", content_type="text/plain", size=3
        )

        self.assertEqual(2, docs.items.count())


class ArticleTest(TembaTest):
    def create_article(self, knowledge, title: str, *, parent=None, status=Article.STATUS_DRAFT):
        return Article.objects.create(
            knowledge=knowledge,
            parent=parent,
            title=title,
            slug=Article.get_unique_slug(knowledge, title),
            status=status,
            created_by=self.admin,
            modified_by=self.admin,
        )

    def setUp(self):
        super().setUp()

        self.helpdesk = self.org.knowledge.get(knowledge_type=Knowledge.TYPE_HELPDESK)

    def test_get_unique_slug(self):
        self.assertEqual("getting-started", Article.get_unique_slug(self.helpdesk, "Getting Started"))

        article = self.create_article(self.helpdesk, "Getting Started")
        self.assertEqual("getting-started", article.slug)
        self.assertEqual(self.org, article.org)

        # a collision gets a numeric suffix
        self.assertEqual("getting-started-2", Article.get_unique_slug(self.helpdesk, "Getting Started"))

        # unless it's with ourselves
        self.assertEqual("getting-started", Article.get_unique_slug(self.helpdesk, "Getting Started", ignore=article))

        # a title that slugifies to nothing falls back to "article"
        self.assertEqual("article", Article.get_unique_slug(self.helpdesk, "!!!"))

        # long slugs are truncated to make room for a suffix
        long_title = "x" * 255
        self.assertEqual("x" * 255, Article.get_unique_slug(self.helpdesk, long_title))
        self.create_article(self.helpdesk, long_title)
        self.assertEqual("x" * 253 + "-2", Article.get_unique_slug(self.helpdesk, long_title))

        # a released article's slug is free for re-use
        article.release(self.admin)
        self.assertEqual("getting-started", Article.get_unique_slug(self.helpdesk, "Getting Started"))

    def test_unique_slugs(self):
        self.create_article(self.helpdesk, "Getting Started")

        with self.assertRaises(IntegrityError):
            Article.objects.create(
                knowledge=self.helpdesk,
                title="Getting Started",
                slug="getting-started",
                created_by=self.admin,
                modified_by=self.admin,
            )

    def test_create(self):
        article1 = Article.create(self.helpdesk, self.admin, "Getting Started")

        self.assertEqual(self.helpdesk, article1.knowledge)
        self.assertIsNone(article1.parent)
        self.assertEqual(0, article1.sort_order)
        self.assertEqual("getting-started", article1.slug)
        self.assertEqual("", article1.body)
        self.assertEqual(Article.STATUS_DRAFT, article1.status)  # new articles are always drafts
        self.assertIsNone(article1.published_on)
        self.assertEqual("eng", article1.language)  # defaults to the workspace's primary flow language

        # new articles go to the end of their level so creating one never reshuffles the tree
        article2 = Article.create(self.helpdesk, self.admin, "Flows", body="# Flows", language="spa")
        self.assertEqual(1, article2.sort_order)
        self.assertEqual("# Flows", article2.body)
        self.assertEqual("spa", article2.language)

        child = Article.create(self.helpdesk, self.admin, "Nodes", parent=article2)
        self.assertEqual(article2, child.parent)
        self.assertEqual(0, child.sort_order)

    def test_get_tree(self):
        flows = self.create_article(self.helpdesk, "Flows")
        contacts = self.create_article(self.helpdesk, "Contacts")
        nodes = self.create_article(self.helpdesk, "Nodes", parent=flows)
        edges = self.create_article(self.helpdesk, "Edges", parent=flows)
        deleted = self.create_article(self.helpdesk, "Old", parent=flows)

        Article.objects.filter(id=contacts.id).update(sort_order=1)
        Article.objects.filter(id=nodes.id).update(sort_order=1)
        deleted.release(self.admin)

        tree = Article.get_tree(self.helpdesk)

        # depth first, siblings by sort order then title, and released articles omitted
        self.assertEqual([flows, edges, nodes, contacts], tree)
        self.assertEqual([0, 1, 1, 0], [a.depth for a in tree])
        self.assertEqual([None, flows.uuid, flows.uuid, None], [a.parent_uuid for a in tree])

        # an article orphaned by its parent going inactive is shown as a root rather than dropped - otherwise it would
        # be invisible here, and so unmovable, while still being indexed if it were published
        Article.objects.filter(id=flows.id).update(is_active=False)

        tree = Article.get_tree(self.helpdesk)

        self.assertEqual([edges, contacts, nodes], tree)
        self.assertEqual([0, 0, 0], [a.depth for a in tree])

        # and shown as a root means shown with no parent, rather than naming one that isn't in the tree
        self.assertEqual([None, None, None], [a.parent_uuid for a in tree])

    def test_apply_sort(self):
        flows = self.create_article(self.helpdesk, "Flows")
        contacts = self.create_article(self.helpdesk, "Contacts")
        nodes = self.create_article(self.helpdesk, "Nodes")
        other = self.create_article(self.org2.knowledge.get(knowledge_type=Knowledge.TYPE_HELPDESK), "Other")
        modified_on = flows.modified_on

        Article.apply_sort(
            self.helpdesk,
            [(str(contacts.uuid), None, 0), (str(flows.uuid), None, 1), (str(nodes.uuid), str(flows.uuid), 0)],
        )

        self.assertEqual([contacts, flows, nodes], Article.get_tree(self.helpdesk))
        self.assertEqual([0, 0, 1], [a.depth for a in Article.get_tree(self.helpdesk)])

        # reordering isn't something mailroom indexes, so it doesn't make articles look stale
        flows.refresh_from_db()
        self.assertEqual(modified_on, flows.modified_on)

        # an article we don't own can't be moved into our tree, or be made a parent in it
        with self.assertRaises(ValueError):
            Article.apply_sort(self.helpdesk, [(str(other.uuid), None, 0)])
        with self.assertRaises(ValueError):
            Article.apply_sort(self.helpdesk, [(str(flows.uuid), str(other.uuid), 0)])

        # nor can an article be its own ancestor
        with self.assertRaises(ValueError):
            Article.apply_sort(self.helpdesk, [(str(flows.uuid), str(flows.uuid), 0)])
        with self.assertRaises(ValueError):
            Article.apply_sort(
                self.helpdesk, [(str(flows.uuid), str(contacts.uuid), 0), (str(contacts.uuid), str(flows.uuid), 0)]
            )

        # nesting is allowed up to the cap...
        deep = self.create_article(self.helpdesk, "Deep")
        deeper = self.create_article(self.helpdesk, "Deeper")
        Article.apply_sort(self.helpdesk, [(str(deep.uuid), str(nodes.uuid), 0)])

        # ...but no further, counting the parts of the tree the client didn't mention
        with self.assertRaises(ValueError):
            Article.apply_sort(self.helpdesk, [(str(deeper.uuid), str(deep.uuid), 0)])

        # none of the rejected moves changed anything
        self.assertEqual([contacts, deeper, flows, nodes, deep], Article.get_tree(self.helpdesk))
        self.assertEqual([0, 0, 0, 1, 2], [a.depth for a in Article.get_tree(self.helpdesk)])

    def test_as_html(self):
        article = self.create_article(self.helpdesk, "Getting Started")

        article.body = "# Heading\n\nSome **bold** text with a [link](https://nyaruka.com).\n\n* one\n* two"
        self.assertEqual(
            '<h1>Heading</h1>\n<p>Some <strong>bold</strong> text with a <a href="https://nyaruka.com" '
            'rel="noopener noreferrer">link</a>.</p>\n<ul>\n<li>one</li>\n<li>two</li>\n</ul>',
            article.as_html(),
        )

        # tables and fenced code blocks are rendered
        article.body = "| a | b |\n| - | - |\n| 1 | 2 |"
        self.assertIn("<table>", article.as_html())

        # raw HTML in the source is sanitized, as are the javascript: URLs markdown will make a link out of
        article.body = "<script>alert(1)</script><p onclick='x'>hi</p>\n\n[bad](javascript:alert(1))"
        self.assertEqual('\n<p>hi</p>\n\n<p><a rel="noopener noreferrer">bad</a></p>', article.as_html())

        # images survive, since screenshots are the point of them
        article.body = "![shot](https://example.com/shot.png)"
        self.assertEqual('<p><img alt="shot" src="https://example.com/shot.png"></p>', article.as_html())

    def test_publishing(self):
        article = self.create_article(self.helpdesk, "Getting Started")
        modified_on = article.modified_on

        article.publish(self.editor)

        article.refresh_from_db()
        self.assertEqual(Article.STATUS_PUBLISHED, article.status)
        self.assertIsNotNone(article.published_on)
        self.assertEqual(self.editor, article.modified_by)
        self.assertGreater(article.modified_on, modified_on)

        modified_on = article.modified_on
        article.unpublish(self.admin)

        # modified_on bumps so mailroom's sweep sees the source as stale and drops the chunks
        article.refresh_from_db()
        self.assertEqual(Article.STATUS_DRAFT, article.status)
        self.assertIsNone(article.published_on)
        self.assertGreater(article.modified_on, modified_on)

    @cleanup(s3=True)
    def test_release(self):
        parent = self.create_article(self.helpdesk, "Flows", status=Article.STATUS_PUBLISHED)
        child1 = self.create_article(self.helpdesk, "Nodes", parent=parent)
        child2 = self.create_article(self.helpdesk, "Edges", parent=parent)
        modified_on = parent.modified_on

        path = public_file_storage.save(
            get_article_image_path(parent, uuid4(), "image/png"), SimpleUploadedFile("shot.png", b"png")
        )
        ArticleImage.objects.create(
            article=parent, name="shot.png", path=path, content_type="image/png", size=3, created_by=self.admin
        )

        parent.release(self.admin)

        # soft deleted, back to draft, and modified_on bumped so mailroom's sweep sees the tombstone
        parent.refresh_from_db()
        self.assertFalse(parent.is_active)
        self.assertEqual(Article.STATUS_DRAFT, parent.status)
        self.assertIsNone(parent.published_on)
        self.assertGreater(parent.modified_on, modified_on)

        # children reparented to our parent (the root) so the tree stays connected
        child1.refresh_from_db()
        child2.refresh_from_db()
        self.assertIsNone(child1.parent)
        self.assertIsNone(child2.parent)

        # and our images are gone for good - rows first, then the storage objects
        self.assertEqual(0, ArticleImage.objects.count())
        self.assertFalse(public_file_storage.exists(path))


class ArticleImageTest(TembaTest):
    @cleanup(s3=True)
    def test_from_upload(self):
        helpdesk = self.org.knowledge.get(knowledge_type=Knowledge.TYPE_HELPDESK)
        article = Article.create(helpdesk, self.admin, "Getting Started")

        image = ArticleImage.from_upload(
            article, self.admin, SimpleUploadedFile("Screen Shot!.PNG", b"png", content_type="image/png")
        )

        self.assertEqual(article, image.article)
        self.assertEqual("Screen Shot.PNG", image.name)  # cleaned
        self.assertEqual(
            f"orgs/{self.org.id}/knowledge/{helpdesk.uuid}/articles/{article.uuid}/{image.uuid}.png", image.path
        )
        self.assertEqual("image/png", image.content_type)
        self.assertEqual(3, image.size)
        self.assertTrue(public_file_storage.exists(image.path))

        # the stored key's extension comes from the sniffed type, never the uploaded name - these live in a public
        # bucket which serves an object as whatever its extension implies, so a .html name would be served as HTML
        image = ArticleImage.from_upload(
            article, self.admin, SimpleUploadedFile("evil.html", b"png", content_type="image/png")
        )

        self.assertEqual("evil.html", image.name)
        self.assertTrue(image.path.endswith(f"{image.uuid}.png"))

    @cleanup(s3=True)
    def test_delete(self):
        helpdesk = self.org.knowledge.get(knowledge_type=Knowledge.TYPE_HELPDESK)
        article = Article.objects.create(
            knowledge=helpdesk,
            title="Getting Started",
            slug="getting-started",
            created_by=self.admin,
            modified_by=self.admin,
        )

        image_uuid = uuid4()
        path = public_file_storage.save(
            get_article_image_path(article, image_uuid, "image/png"), SimpleUploadedFile("shot1.png", b"png")
        )
        self.assertEqual(f"orgs/{self.org.id}/knowledge/{helpdesk.uuid}/articles/{article.uuid}/{image_uuid}.png", path)
        image = ArticleImage.objects.create(
            article=article, name="shot1.png", path=path, content_type="image/png", size=3, created_by=self.admin
        )

        self.assertEqual(public_file_storage.url(path), image.url)

        image.delete()

        self.assertEqual(0, ArticleImage.objects.count())
        self.assertFalse(public_file_storage.exists(path))
