import os
import re
from pathlib import Path

from pgvector.django import HnswIndex, VectorField

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models, transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from temba.orgs.models import Org
from temba.utils.models import TembaModel, delete_in_batches
from temba.utils.s3 import public_file_storage
from temba.utils.uuid import uuid4


class Knowledge(TembaModel):
    """
    A source of knowledge that AI agents can search semantically.

    Indexing - crawling, extracting, chunking and embedding - is performed entirely by mailroom, which sweeps for rows
    needing work. This app owns the schema, the CRUD UI and document uploads only; it never calls an embeddings service.
    """

    # authored types - items live in their own Django-owned table, mailroom only reads
    TYPE_SHORTCUTS = "shortcuts"  # the org's shortcuts, read by mailroom straight from tickets_shortcut
    TYPE_HELPDESK = "helpdesk"  # the org's own help articles, read from tickets_article
    # ingested types - items share tickets_knowledgeitem, mailroom owns the lifecycle
    TYPE_WEBSITE = "website"  # a crawled website
    TYPE_DOCUMENTS = "documents"  # uploaded files
    TYPE_CHOICES = (
        (TYPE_SHORTCUTS, _("Shortcuts")),
        (TYPE_HELPDESK, _("Helpdesk")),
        (TYPE_WEBSITE, _("Website")),
        (TYPE_DOCUMENTS, _("Documents")),
    )

    SYSTEM_TYPES = (TYPE_SHORTCUTS, TYPE_HELPDESK)  # one of each per org, created in Org.initialize()
    SYSTEM_NAMES = {TYPE_SHORTCUTS: "Shortcuts", TYPE_HELPDESK: "Helpdesk"}

    STATUS_PENDING = "P"  # needs (re)indexing, mailroom's sweep will pick it up
    STATUS_INDEXING = "I"  # mailroom is working on it
    STATUS_READY = "R"  # indexed and searchable
    STATUS_FAILED = "F"  # last indexing attempt failed, see error
    STATUS_CHOICES = (
        (STATUS_PENDING, _("Pending")),
        (STATUS_INDEXING, _("Indexing")),
        (STATUS_READY, _("Ready")),
        (STATUS_FAILED, _("Failed")),
    )

    REFRESH_NEVER = "never"
    REFRESH_DAILY = "daily"
    REFRESH_WEEKLY = "weekly"
    REFRESH_MONTHLY = "monthly"
    REFRESH_CHOICES = (
        (REFRESH_NEVER, _("Never")),
        (REFRESH_DAILY, _("Daily")),
        (REFRESH_WEEKLY, _("Weekly")),
        (REFRESH_MONTHLY, _("Monthly")),
    )

    # config keys for TYPE_WEBSITE
    CONFIG_URL = "url"
    CONFIG_MAX_DEPTH = "max_depth"
    CONFIG_MAX_PAGES = "max_pages"
    CONFIG_REFRESH = "refresh"

    DEFAULT_MAX_DEPTH = 3
    DEFAULT_MAX_PAGES = 500
    MAX_MAX_PAGES = 5_000
    MAX_URL_LEN = 2048

    org = models.ForeignKey(Org, on_delete=models.PROTECT, related_name="knowledge")
    knowledge_type = models.CharField(max_length=16, choices=TYPE_CHOICES)

    # type specific settings, e.g. for website: url, max_depth, max_pages, refresh. Empty for other types.
    config = models.JSONField(default=dict)

    # everything below is written by mailroom as it indexes - this app only reads it
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error = models.CharField(max_length=255, null=True)
    last_indexed_on = models.DateTimeField(null=True)
    num_items = models.IntegerField(default=0)
    num_chunks = models.IntegerField(default=0)

    org_limit_key = Org.LIMIT_KNOWLEDGE

    @classmethod
    def create_system(cls, org):
        """
        Creates the org's two system sources - its shortcut list and its helpdesk.
        """
        assert not org.knowledge.filter(knowledge_type__in=cls.SYSTEM_TYPES).exists(), (
            "org already has system knowledge"
        )

        return [
            org.knowledge.create(
                name=cls.SYSTEM_NAMES[t],
                knowledge_type=t,
                is_system=True,
                created_by=org.created_by,
                modified_by=org.modified_by,
            )
            for t in cls.SYSTEM_TYPES
        ]

    @classmethod
    def create_website(cls, org, user, name: str, url: str, *, max_depth=None, max_pages=None, refresh=None):
        assert cls.is_valid_name(name), f"'{name}' is not a valid knowledge name"
        assert not org.knowledge.filter(name__iexact=name, is_active=True).exists()

        return org.knowledge.create(
            name=name,
            knowledge_type=cls.TYPE_WEBSITE,
            config={
                cls.CONFIG_URL: url,
                cls.CONFIG_MAX_DEPTH: max_depth or cls.DEFAULT_MAX_DEPTH,
                cls.CONFIG_MAX_PAGES: max_pages or cls.DEFAULT_MAX_PAGES,
                cls.CONFIG_REFRESH: refresh or cls.REFRESH_WEEKLY,
            },
            created_by=user,
            modified_by=user,
        )

    @classmethod
    def create_documents(cls, org, user, name: str):
        assert cls.is_valid_name(name), f"'{name}' is not a valid knowledge name"
        assert not org.knowledge.filter(name__iexact=name, is_active=True).exists()

        # nothing to index until files are uploaded
        return org.knowledge.create(
            name=name,
            knowledge_type=cls.TYPE_DOCUMENTS,
            status=cls.STATUS_READY,
            created_by=user,
            modified_by=user,
        )

    @property
    def url(self) -> str:
        return self.config.get(self.CONFIG_URL)

    def mark_pending(self):
        """
        Flags this source as needing (re)indexing so mailroom's sweep picks it up. Called whenever this app changes
        something mailroom's index is derived from - website config, uploaded files.
        """
        self.status = self.STATUS_PENDING
        self.error = None
        self.save(update_fields=("status", "error"))

    def release(self, user):
        assert not (self.is_system and self.org.is_active), "can't release system knowledge"

        # deactivate first so nothing reads or indexes it while we purge
        self.is_active = False
        self.name = self._deleted_name()
        self.num_items = 0
        self.num_chunks = 0
        self.modified_by = user
        self.save(update_fields=("name", "is_active", "num_items", "num_chunks", "modified_by", "modified_on"))

        self._purge()

    def delete(self):
        self._purge()

        super().delete()

    def _purge(self):
        """
        Removes this source's chunks, items, articles and article images. Rows go first; storage objects are only
        removed once their rows are gone.
        """
        # collect storage keys before the rows that name them disappear - two different buckets
        item_paths = list(self.items.exclude(path=None).values_list("path", flat=True))
        image_paths = list(ArticleImage.objects.filter(article__knowledge=self).values_list("path", flat=True))

        delete_in_batches(self.chunks.all())
        delete_in_batches(self.items.all())
        delete_in_batches(ArticleImage.objects.filter(article__knowledge=self))

        # parent is PROTECT so flatten the article tree before deleting it
        self.articles.exclude(parent=None).update(parent=None)
        delete_in_batches(self.articles.all())

        for path in item_paths:
            default_storage.delete(path)
        for path in image_paths:
            public_file_storage.delete(path)

    class Meta:
        constraints = [models.UniqueConstraint("org", Lower("name"), name="unique_knowledge_names")]
        indexes = [
            # mailroom's indexing sweep's worklist
            models.Index(name="knowledge_pending", fields=("id",), condition=Q(is_active=True, status="P")),
        ]


class Article(models.Model):
    """
    An article in an org's helpdesk. Written by this app, read by mailroom, which indexes only published, active
    articles.

    Deliberately not a TembaModel: TembaModel.name is capped at 64 chars and NameValidator rejects " and \\, which real
    help titles routinely contain. Soft-deleted like Shortcut so mailroom's delta sweep sees the tombstone - a hard
    delete would leave its chunks stranded until a full reindex.
    """

    STATUS_DRAFT = "D"  # never indexed, never public
    STATUS_PUBLISHED = "P"
    STATUS_CHOICES = ((STATUS_DRAFT, _("Draft")), (STATUS_PUBLISHED, _("Published")))

    MAX_TITLE_LEN = 255
    MAX_SLUG_LEN = 255
    MAX_DEPTH = 3  # root + two levels of nesting; enforced by the (phase 4) reorder view

    uuid = models.UUIDField(unique=True, default=uuid4)
    knowledge = models.ForeignKey(Knowledge, on_delete=models.PROTECT, related_name="articles")

    # the tree - a plain self-FK, not mptt (that dep exists only for locations and buys nothing at help-centre depth).
    # Depth is capped at MAX_DEPTH and cycles are rejected server-side.
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, related_name="children")
    sort_order = models.IntegerField(default=0)

    title = models.CharField(max_length=MAX_TITLE_LEN)
    slug = models.SlugField(max_length=MAX_SLUG_LEN)
    body = models.TextField(default="")  # markdown source

    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    published_on = models.DateTimeField(null=True)

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_on = models.DateTimeField(default=timezone.now)
    modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    # auto_now is load-bearing: mailroom's staleness sweep is MAX(modified_on) > knowledge.last_indexed_on, so an
    # unpublish or a soft-delete has to bump it for the removal to be noticed
    modified_on = models.DateTimeField(auto_now=True)

    @classmethod
    def get_unique_slug(cls, knowledge, title: str, ignore=None) -> str:
        base = slugify(title)[: cls.MAX_SLUG_LEN] or "article"
        qs = cls.objects.filter(knowledge=knowledge, is_active=True)
        if ignore:
            qs = qs.exclude(id=ignore.id)

        slug, count = base, 1
        while qs.filter(slug=slug).exists():
            count += 1
            suffix = f"-{count}"
            slug = f"{base[: cls.MAX_SLUG_LEN - len(suffix)]}{suffix}"

        return slug

    @property
    def org(self):
        return self.knowledge.org

    def release(self, user):
        """
        Soft delete. Children are reparented to our parent so the tree stays connected.
        """
        self.children.update(parent=self.parent)

        self.is_active = False
        self.status = self.STATUS_DRAFT
        self.modified_by = user
        self.save(update_fields=("is_active", "status", "modified_by", "modified_on"))

    class Meta:
        constraints = [
            models.UniqueConstraint("knowledge", "slug", condition=Q(is_active=True), name="unique_article_slugs")
        ]
        indexes = [
            # the tree, in display order
            models.Index(name="article_by_tree", fields=("knowledge", "parent", "sort_order")),
            # mailroom's staleness + delta sweep
            models.Index(name="article_by_modified", fields=("knowledge", "modified_on")),
        ]


def get_article_image_path(article, image_uuid, filename: str) -> str:
    return (
        f"orgs/{article.knowledge.org_id}/knowledge/{article.knowledge.uuid}/"
        f"articles/{article.uuid}/{image_uuid}{Path(filename).suffix.lower()}"
    )


class ArticleImage(models.Model):
    """
    A screenshot uploaded to an article and referenced from its markdown by URL. Stored in public storage because the
    eventual standalone help site serves these directly.
    """

    uuid = models.UUIDField(unique=True, default=uuid4)
    article = models.ForeignKey(Article, on_delete=models.PROTECT, related_name="images")
    name = models.CharField(max_length=255)
    path = models.CharField(max_length=2048)  # key in the public bucket
    content_type = models.CharField(max_length=255)
    size = models.IntegerField()

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_on = models.DateTimeField(default=timezone.now)

    @property
    def url(self) -> str:
        return public_file_storage.url(self.path)

    def delete(self):
        path = self.path

        super().delete()

        # only remove the storage object once the row is gone
        public_file_storage.delete(path)


def get_knowledge_item_path(knowledge, item_uuid, filename: str) -> str:
    return f"orgs/{knowledge.org_id}/knowledge/{knowledge.uuid}/{item_uuid}{Path(filename).suffix.lower()}"


class KnowledgeItem(models.Model):
    """
    One page or one uploaded document in an ingested knowledge source.

    Writers are split: this app creates document rows on upload (url null, path set); mailroom creates page rows as it
    crawls (url set) and owns status/error/num_chunks for both. A page's uuid is stable across recrawls because rows
    are matched by normalised url within the source - that's what makes incremental reindexing possible, since chunks
    key off that uuid.
    """

    ALLOWED_CONTENT_TYPES = (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
        "text/csv",
        "text/markdown",
        "text/plain",
    )
    MAX_UPLOAD_SIZE = 1024 * 1024 * 20  # 20MB
    MAX_DOCUMENTS = 100  # per documents source

    STATUS_PENDING = "P"
    STATUS_INDEXING = "I"
    STATUS_READY = "R"
    STATUS_FAILED = "F"
    STATUS_CHOICES = (
        (STATUS_PENDING, _("Pending")),
        (STATUS_INDEXING, _("Indexing")),
        (STATUS_READY, _("Ready")),
        (STATUS_FAILED, _("Failed")),
    )

    uuid = models.UUIDField(unique=True, default=uuid4)
    knowledge = models.ForeignKey(Knowledge, on_delete=models.PROTECT, related_name="items")
    name = models.CharField(max_length=255)  # page title, or the cleaned original filename

    # null for uploads; the normalised page URL for crawled pages, and their identity within the source
    url = models.URLField(max_length=2048, null=True)

    # storage key: set for uploads (private bucket); optionally the cached extracted text for pages
    path = models.CharField(max_length=2048, null=True)

    content_type = models.CharField(max_length=255)  # mailroom sets text/html for pages
    size = models.IntegerField()  # bytes of the stored/fetched content

    # written by mailroom as it extracts and chunks
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error = models.CharField(max_length=255, null=True)
    num_chunks = models.IntegerField(default=0)

    created_by = models.ForeignKey(  # null for crawled pages - nobody uploaded them
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    created_on = models.DateTimeField(default=timezone.now)

    @classmethod
    def is_allowed_type(cls, content_type: str) -> bool:
        return content_type in cls.ALLOWED_CONTENT_TYPES

    @classmethod
    def clean_name(cls, filename: str) -> str:
        base_name, extension = os.path.splitext(filename)
        base_name = re.sub(r"[^\w\-\[\]\(\) ]", "", base_name).strip()[:200] or "file"
        return base_name + extension[:50]

    @classmethod
    def from_upload(cls, knowledge, user, file):
        assert knowledge.knowledge_type == Knowledge.TYPE_DOCUMENTS, "can only upload to documents knowledge"
        assert cls.is_allowed_type(file.content_type), "unsupported content type"

        uuid = uuid4()
        path = default_storage.save(get_knowledge_item_path(knowledge, uuid, file.name), file)

        obj = cls.objects.create(
            uuid=uuid,
            knowledge=knowledge,
            name=cls.clean_name(file.name),
            url=None,  # explicit: this is what makes it a document rather than a page
            path=path,
            content_type=file.content_type,
            size=default_storage.size(path),
            created_by=user,
        )

        knowledge.mark_pending()
        return obj

    @property
    def org(self):
        return self.knowledge.org

    def delete(self):
        path = self.path

        with transaction.atomic():
            # this item's chunks are no longer valid - mailroom will recompute the source's counters
            delete_in_batches(self.knowledge.chunks.filter(item_key=self.uuid))
            super().delete()
            self.knowledge.mark_pending()

        # only remove the storage object once the deletion has committed
        if path:
            default_storage.delete(path)

    class Meta:
        constraints = [
            # a page's identity within its source. Postgres treats NULLs as distinct in a unique index, so uploaded
            # documents (url null) are exempt automatically - no partial-index condition needed, and any number of
            # documents can coexist in one source.
            models.UniqueConstraint("knowledge", "url", name="unique_knowledge_item_urls"),
        ]


class KnowledgeChunk(models.Model):
    """
    A chunk of indexed content with its embedding. Rows are written exclusively by mailroom - this app never INSERTs
    or UPDATEs them. It only DELETEs them when the user deletes the owning item or source.
    """

    EMBEDDING_DIMENSIONS = 384  # intfloat/multilingual-e5-small

    knowledge = models.ForeignKey(Knowledge, on_delete=models.PROTECT, related_name="chunks")

    # the owning item's uuid. Not an FK, because the item lives in a different table per source type: KnowledgeItem
    # for pages/documents, Shortcut for shortcuts, Article for helpdesk. One mechanism spanning all four beats an FK
    # plus fallbacks.
    item_key = models.UUIDField()
    item_name = models.CharField(max_length=255)
    item_url = models.URLField(max_length=2048, null=True)

    text = models.TextField()
    embedding = VectorField(dimensions=EMBEDDING_DIMENSIONS)

    class Meta:
        indexes = [
            # a single ANN index shared by all orgs and sources - queries filtered by knowledge source rely on
            # pgvector >= 0.8 iterative scans (enforced by migration 0092) to return complete results
            HnswIndex(
                name="knowledgechunk_embedding",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=("vector_cosine_ops",),
            ),
            # lets mailroom replace one item's chunks on reindex, and lets us delete one item's chunks
            models.Index(name="knowledgechunk_by_item", fields=("knowledge", "item_key")),
        ]
