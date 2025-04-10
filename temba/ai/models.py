from abc import ABCMeta

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.template import Engine
from django.urls import re_path

from temba import mailroom
from temba.orgs.models import DependencyMixin, Org
from temba.utils.models import TembaModel


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


class LLM(TembaModel, DependencyMixin):
    """
    A language model that can be used for AI tasks
    """

    org = models.ForeignKey(Org, related_name="llms", on_delete=models.PROTECT)
    llm_type = models.CharField(max_length=16)
    model = models.CharField(max_length=64)
    config = models.JSONField()

    org_limit_key = Org.LIMIT_LLMS

    @classmethod
    def create(cls, org, user, typ, model: str, name: str, config: dict):
        assert "models" not in typ.settings or model in typ.settings["models"]

        return cls.objects.create(
            org=org,
            name=name,
            llm_type=typ.slug,
            model=model,
            config=config,
            created_by=user,
            modified_by=user,
        )

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

    def translate(self, from_language: str, to_language: str, text: str) -> str:
        return mailroom.get_client().llm_translate(self, from_language, to_language, text)["text"]

    def release(self, user):
        super().release(user)

        self.is_active = False
        self.name = self._deleted_name()
        self.modified_by = user
        self.save(update_fields=("name", "is_active", "modified_by", "modified_on"))

    class Meta:
        constraints = [models.UniqueConstraint("org", Lower("name"), name="unique_llm_names")]
