from abc import ABCMeta

from django.db import models
from django.template import Engine
from django.urls import re_path

from temba.orgs.models import DependencyMixin, Org
from temba.utils.models import TembaModel


class LLM(TembaModel, DependencyMixin):
    """
    A language model that can be used for AI tasks
    """

    org = models.ForeignKey(Org, related_name="llms", on_delete=models.PROTECT)
    name = models.CharField(max_length=64, help_text="The user's name for the LLM model")
    type = models.CharField(max_length=16)
    config = models.JSONField()

    org = models.ForeignKey(
        Org, on_delete=models.CASCADE, related_name="llm_models", help_text="The organization this LLM model belongs to"
    )

    @classmethod
    def create(cls, org, user, ai_type, name, api_key, model, config=None):
        if config is None:
            config = {}

        config["api_key"] = api_key
        config["model"] = model

        ai = cls.objects.create(
            org=org,
            name=name,
            type=ai_type,
            config=config,
            created_by=user,
            modified_by=user,
        )

        return ai

    def get_api_key(self):
        """
        Returns the API key for this LLM
        """
        return self.config.get("api_key")

    def get_model_name(self):
        """
        Returns the model name for this LLM
        """
        return self.config.get("model_name")

    def get_type(self):
        """
        Returns the type instance for this AI model
        """
        from .types import get_ai_types

        return get_ai_types()[self.type]

    def release(self, user):
        super().release(user)

        self.is_active = False
        self.name = self._deleted_name()
        self.modified_by = user
        self.save(update_fields=("name", "is_active", "modified_by", "modified_on"))

    def __str__(self):
        return f"{self.name} ({self.type})"

    @classmethod
    def get_types(cls):
        """
        Returns the possible types available for classifiers
        :return:
        """
        from .types import TYPES

        return TYPES.values()


class LLMType(metaclass=ABCMeta):
    """
    Base type for all LLM model types
    """

    # icon to show in UI
    icon = "icon-llm"

    # the view that handles connection of a new model
    connect_view = None

    # the blurb to show on the list page
    connect_blurb = None

    # the blurb to show on the connect form page
    form_blurb = None

    def get_icon(self):
        return self.icon

    def get_form_blurb(self):
        """
        Gets the blurb to show on the connect form
        """
        return Engine.get_default().from_string(self.form_blurb)

    def get_urls(self):
        """
        Returns all the URLs this classifier exposes to Django, the URL should be relative.
        """
        return [self.get_connect_url()]

    def get_connect_url(self):
        """
        Gets the URL/view configuration for this classifier's connect page
        """
        return re_path(r"^connect", self.connect_view.as_view(llm_type=self), name="connect")

    def get_connect_blurb(self):
        """
        Gets the blurb for use on the connect page
        """
        return Engine.get_default().from_string(self.connect_blurb)
