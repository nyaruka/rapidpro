from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError

from temba.ai.models import Article, ArticleChunk, KnowledgeBase, get_document_path
from temba.tests import TembaTest


class KnowledgeBaseTest(TembaTest):
    def test_create(self):
        kb1 = KnowledgeBase.create_website(self.org, self.admin, "Docs", "https://docs.example.com")
        kb2 = KnowledgeBase.create_documents(self.org, self.admin, "Manuals")
        kb3 = KnowledgeBase.create_faq(self.org, self.admin, "Common Questions")

        self.assertEqual("Docs", kb1.name)
        self.assertEqual(KnowledgeBase.TYPE_WEBSITE, kb1.kb_type)
        self.assertEqual("https://docs.example.com", kb1.url)
        self.assertEqual(KnowledgeBase.STATUS_PENDING, kb1.status)
        self.assertEqual({}, kb1.crawl_state)
        self.assertEqual(0, kb1.num_pages)
        self.assertEqual(0, kb1.num_articles)
        self.assertEqual(0, kb1.num_chunks)
        self.assertEqual(0, kb1.content_chars)
        self.assertIsNone(kb1.started_on)
        self.assertIsNone(kb1.finished_on)

        # documents and FAQ knowledge bases start out complete since there's nothing to process yet
        self.assertEqual(KnowledgeBase.TYPE_DOCUMENTS, kb2.kb_type)
        self.assertIsNone(kb2.url)
        self.assertEqual(KnowledgeBase.STATUS_COMPLETE, kb2.status)
        self.assertEqual(KnowledgeBase.TYPE_FAQ, kb3.kb_type)
        self.assertIsNone(kb3.url)
        self.assertEqual(KnowledgeBase.STATUS_COMPLETE, kb3.status)

    def test_is_finished(self):
        kb = KnowledgeBase.create_website(self.org, self.admin, "Docs", "https://docs.example.com")

        self.assertFalse(kb.is_finished)

        kb.status = KnowledgeBase.STATUS_PROCESSING
        self.assertFalse(kb.is_finished)

        kb.status = KnowledgeBase.STATUS_COMPLETE
        self.assertTrue(kb.is_finished)

        kb.status = KnowledgeBase.STATUS_FAILED
        self.assertTrue(kb.is_finished)

    def test_unique_names(self):
        KnowledgeBase.create_documents(self.org, self.admin, "Manuals")

        # name uniqueness is case-insensitive within an org
        KnowledgeBase.create_documents(self.org2, self.admin2, "MANUALS")

        with self.assertRaises(IntegrityError):
            KnowledgeBase.create_documents(self.org, self.admin, "MANUALS")

    def test_release(self):
        kb = KnowledgeBase.create_documents(self.org, self.admin, "Manuals")

        kb.release(self.admin)

        self.assertFalse(kb.is_active)
        self.assertTrue(kb.name.startswith("deleted-"))

        # name is now free to be reused
        KnowledgeBase.create_documents(self.org, self.admin, "Manuals")

    def test_delete(self):
        kb = KnowledgeBase.create_website(self.org, self.admin, "Docs", "https://docs.example.com")
        article1 = Article.objects.create(
            knowledge_base=kb, url="https://docs.example.com/start", title="Start", content="Getting started..."
        )
        article2 = Article.objects.create(
            knowledge_base=kb, file=SimpleUploadedFile("guide.pdf", b"PDF"), title="Guide", content="How to..."
        )
        ArticleChunk.objects.create(
            article=article1,
            knowledge_base=kb,
            text="Getting started...",
            embedding=[0.0] * ArticleChunk.EMBEDDING_DIMENSIONS,
        )
        file_path = article2.file.name
        storage = article2.file.storage
        self.assertTrue(storage.exists(file_path))

        kb.delete()

        self.assertEqual(0, ArticleChunk.objects.count())
        self.assertEqual(0, Article.objects.count())
        self.assertEqual(0, KnowledgeBase.objects.count())
        self.assertFalse(storage.exists(file_path))


class ArticleTest(TembaTest):
    def test_document_path(self):
        kb = KnowledgeBase.create_documents(self.org, self.admin, "Manuals")
        article = Article.objects.create(knowledge_base=kb, title="Manual", content="How to...")

        path = get_document_path(article, "User Manual.PDF")

        self.assertTrue(path.startswith(f"orgs/{self.org.id}/knowledge_bases/{kb.uuid}/"))
        self.assertTrue(path.endswith(".pdf"))

    def test_delete(self):
        kb = KnowledgeBase.create_website(self.org, self.admin, "Docs", "https://docs.example.com")
        article1 = Article.objects.create(
            knowledge_base=kb,
            url="https://docs.example.com/start",
            file=SimpleUploadedFile("start.pdf", b"PDF"),
            title="Start",
            content="Getting started...",
        )
        article2 = Article.objects.create(
            knowledge_base=kb, url="https://docs.example.com/faq", title="FAQ", content="Questions..."
        )
        for text in ("Getting", "started..."):
            ArticleChunk.objects.create(
                article=article1, knowledge_base=kb, text=text, embedding=[0.0] * ArticleChunk.EMBEDDING_DIMENSIONS
            )
        ArticleChunk.objects.create(article=article2, knowledge_base=kb, text="Questions...", embedding=[0.0] * 1536)
        file_path = article1.file.name
        storage = article1.file.storage
        self.assertTrue(storage.exists(file_path))

        self.assertEqual(self.org, article1.org)

        article1.delete()

        # counters are recomputed from what remains and the uploaded file is gone
        kb.refresh_from_db()
        self.assertEqual(1, kb.num_articles)
        self.assertEqual(1, kb.num_chunks)
        self.assertEqual(len(article2.content), kb.content_chars)
        self.assertEqual({article2}, set(kb.articles.all()))
        self.assertEqual({article2}, {c.article for c in kb.chunks.all()})
        self.assertFalse(storage.exists(file_path))

        article2.delete()

        kb.refresh_from_db()
        self.assertEqual(0, kb.num_articles)
        self.assertEqual(0, kb.num_chunks)
        self.assertEqual(0, kb.content_chars)
