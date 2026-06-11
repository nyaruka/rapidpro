from abc import ABCMeta
from pathlib import Path

from pgvector.django import HnswIndex, VectorField

from django.conf import settings
from django.contrib.postgres.indexes import OpClass
from django.db import models, transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import Length, Lower
from django.template import Engine
from django.urls import re_path
from django.utils import timezone

from temba import mailroom
from temba.orgs.models import DependencyMixin, Org
from temba.utils.models import TembaModel, delete_in_batches
from temba.utils.models.counts import BaseDailyCount
from temba.utils.uuid import uuid4


class LLMType(metaclass=ABCMeta):
    """
    Base type for all LLM model types
    """

    # icon to show in UI
    icon = "icon-llm"

    # the view that handles connection of a new model
    connect_view = None

    # the blurb to show on the connect form page
    form_blurb = None

    def get_form_blurb(self):
        """
        Gets the blurb to show on the connect form
        """
        return Engine.get_default().from_string(self.form_blurb)

    def get_urls(self):
        """
        Returns all the URLs this llm exposes to Django, the URL should be relative.
        """
        return [re_path(r"^connect", self.connect_view.as_view(llm_type=self), name="connect")]

    @property
    def settings(self) -> dict:
        """
        Gets the deployment level settings for this type
        """

        return settings.LLM_TYPES[self.__module__ + "." + self.__class__.__name__]

    def is_available_to(self, org, user) -> bool:
        """
        Determines whether this LLM type is available to the given user.
        """
        return True


class LLM(TembaModel, DependencyMixin):
    """
    A language model that can be used for AI tasks
    """

    ROLE_EDITING = "T"
    ROLE_ENGINE = "F"
    ROLE_NAMES = {ROLE_EDITING: "editing", ROLE_ENGINE: "engine"}
    DEFAULT_ROLES = ROLE_EDITING + ROLE_ENGINE

    org = models.ForeignKey(Org, related_name="llms", on_delete=models.PROTECT)
    llm_type = models.CharField(max_length=16)
    model = models.CharField(max_length=64)
    max_output_tokens = models.PositiveIntegerField(default=4_096)
    config = models.JSONField()
    roles = models.CharField(max_length=2, default=DEFAULT_ROLES)

    org_limit_key = Org.LIMIT_LLMS

    @classmethod
    def create(cls, org, user, typ, model: str, name: str, config: dict, roles: str = DEFAULT_ROLES):
        models_settings = typ.settings.get("models") or {}
        assert not models_settings or model in models_settings

        kwargs = dict(
            org=org,
            name=name,
            llm_type=typ.slug,
            model=model,
            config=config,
            roles=roles,
            created_by=user,
            modified_by=user,
        )
        if model in models_settings:
            kwargs["max_output_tokens"] = models_settings[model]

        return cls.objects.create(**kwargs)

    @property
    def type(self) -> LLMType:
        return self.get_type_from_code()

    @classmethod
    def get_types(cls):
        from .types import TYPES

        return TYPES.values()

    def get_type_from_code(self):
        """
        Returns the type instance for this AI model
        """
        from .types import TYPES

        return TYPES[self.llm_type]

    def translate(self, source: str, target: str, items: dict[str, list[str]]) -> dict[str, list[str]]:
        return mailroom.get_client().llm_translate(self, source, target, items)

    def release(self, user):
        assert not (self.is_system and self.org.is_active), "can't release system LLMs"

        super().release(user)

        self.is_active = False
        self.name = self._deleted_name()
        self.modified_by = user
        self.save(update_fields=("name", "is_active", "modified_by", "modified_on"))

    def delete(self):
        delete_in_batches(self.counts.all())

        super().delete()

    class Meta:
        constraints = [models.UniqueConstraint("org", Lower("name"), name="unique_llm_names")]


class KnowledgeBase(TembaModel):
    """
    A knowledge base of articles that can be searched semantically via their embedded chunks.
    """

    TYPE_WEBSITE = "W"
    TYPE_DOCUMENTS = "D"
    TYPE_FAQ = "F"
    TYPE_CHOICES = ((TYPE_WEBSITE, "Website"), (TYPE_DOCUMENTS, "Documents"), (TYPE_FAQ, "FAQ"))

    STATUS_PENDING = "P"
    STATUS_PROCESSING = "O"
    STATUS_COMPLETE = "C"
    STATUS_FAILED = "F"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETE, "Complete"),
        (STATUS_FAILED, "Failed"),
    )

    MAX_PAGES = 1_000
    MAX_CONTENT_CHARS = 5_000_000

    org = models.ForeignKey(Org, related_name="knowledge_bases", on_delete=models.PROTECT)
    kb_type = models.CharField(max_length=1, choices=TYPE_CHOICES, default=TYPE_WEBSITE)
    url = models.URLField(max_length=2048, null=True)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error = models.CharField(max_length=255, null=True)
    crawl_state = models.JSONField(default=dict)
    num_pages = models.IntegerField(default=0)
    num_articles = models.IntegerField(default=0)
    num_chunks = models.IntegerField(default=0)
    content_chars = models.IntegerField(default=0)
    started_on = models.DateTimeField(null=True)
    finished_on = models.DateTimeField(null=True)

    @classmethod
    def create_website(cls, org, user, name: str, url: str):
        return cls.objects.create(
            org=org, name=name, kb_type=cls.TYPE_WEBSITE, url=url, created_by=user, modified_by=user
        )

    @classmethod
    def create_documents(cls, org, user, name: str):
        return cls.objects.create(org=org, name=name, kb_type=cls.TYPE_DOCUMENTS, created_by=user, modified_by=user)

    @classmethod
    def create_faq(cls, org, user, name: str):
        return cls.objects.create(org=org, name=name, kb_type=cls.TYPE_FAQ, created_by=user, modified_by=user)

    @property
    def is_finished(self) -> bool:
        return self.status in (self.STATUS_COMPLETE, self.STATUS_FAILED)

    def release(self, user):
        self.is_active = False
        self.name = self._deleted_name()
        self.modified_by = user
        self.save(update_fields=("name", "is_active", "modified_by", "modified_on"))

    def update_counters(self):
        counts = self.articles.aggregate(num=Count("id"), chars=Sum(Length("content")))
        self.num_articles = counts["num"]
        self.num_chunks = self.chunks.count()
        self.content_chars = counts["chars"] or 0
        self.save(update_fields=("num_articles", "num_chunks", "content_chars"))

    def delete(self):
        delete_in_batches(self.chunks.all())

        # articles are bulk deleted below which bypasses Article.delete, so remove uploaded files here
        for article in self.articles.only("id", "file"):
            if article.file:
                article.file.delete(save=False)

        delete_in_batches(self.articles.all())

        super().delete()

    class Meta:
        constraints = [models.UniqueConstraint("org", Lower("name"), name="unique_knowledgebase_names")]


def get_document_path(instance, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return f"orgs/{instance.knowledge_base.org_id}/knowledge_bases/{instance.knowledge_base.uuid}/{uuid4()}{ext}"


class Article(models.Model):
    """
    A unit of content in a knowledge base, e.g. a web page, document or FAQ entry.
    """

    knowledge_base = models.ForeignKey(KnowledgeBase, related_name="articles", on_delete=models.PROTECT)
    url = models.URLField(max_length=2048, null=True)
    file = models.FileField(upload_to=get_document_path, max_length=2048, null=True)
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_on = models.DateTimeField(default=timezone.now)

    @property
    def org(self):
        return self.knowledge_base.org

    def delete(self):
        if self.file:
            self.file.delete(save=False)

        with transaction.atomic():
            delete_in_batches(self.chunks.all())

            super().delete()

            self.knowledge_base.update_counters()


class ArticleChunk(models.Model):
    """
    A chunk of article content with its embedding for semantic search.
    """

    EMBEDDING_DIMENSIONS = 1536  # the model configured by settings.AI_EMBEDDINGS must output vectors of this size

    article = models.ForeignKey(Article, related_name="chunks", on_delete=models.PROTECT)
    knowledge_base = models.ForeignKey(KnowledgeBase, related_name="chunks", on_delete=models.PROTECT)
    text = models.TextField()
    embedding = VectorField(dimensions=EMBEDDING_DIMENSIONS)

    class Meta:
        indexes = [
            HnswIndex(
                name="articlechunk_embedding",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=("vector_cosine_ops",),
            )
        ]


class LLMCount(BaseDailyCount):
    """
    Tracks daily counts of LLM activity (calls and tokens used) by mailroom.
    """

    squash_over = ("llm_id", "day", "scope")

    SCOPE_CALLS = "calls"
    SCOPE_TOKENS_IN = "tokens:in"
    SCOPE_TOKENS_OUT = "tokens:out"

    llm = models.ForeignKey(LLM, on_delete=models.PROTECT, related_name="counts", db_index=False)

    class Meta:
        indexes = [
            models.Index("llm", "day", OpClass("scope", name="varchar_pattern_ops"), name="llmcount_llm_scope"),
            # for squashing task
            models.Index(name="llmcount_unsquashed", fields=("llm", "day", "scope"), condition=Q(is_squashed=False)),
        ]
