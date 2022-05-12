import re
import unicodedata

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count

from temba.orgs.models import DependencyMixin, Org
from temba.utils.fields import KeyValidator
from temba.utils.models import TembaModel
from temba.utils.text import unsnakify


def strip_non_ascii(value: str) -> str:
    """
    Strips non-ASCII values (e.g. accents) from the given text
    """
    text = unicodedata.normalize("NFD", value)
    return text.encode("ascii", "ignore").decode("utf-8")


class Global(TembaModel, DependencyMixin):
    """
    A global is a constant value that can be used in templates in flows and messages.
    """

    MAX_KEY_LEN = 64
    MAX_VALUE_LEN = settings.GLOBAL_VALUE_SIZE

    org = models.ForeignKey(Org, related_name="globals", on_delete=models.PROTECT)
    key = models.CharField(max_length=MAX_KEY_LEN, validators=[KeyValidator(MAX_KEY_LEN)])
    value = models.TextField(max_length=MAX_VALUE_LEN)

    @classmethod
    def create(cls, org, user, name: str, value: str):
        assert cls.is_valid_name(name), f"'{name}' is not valid global name"
        assert not org.globals.filter(name__iexact=name).exists()

        key = cls.name_to_key(name)

        assert cls.is_valid_key(key), f"'{name}' is not valid global key"
        assert not org.globals.filter(key=key).exists()

        return cls.objects.create(org=org, key=key, name=name, value=value, created_by=user, modified_by=user)

    @classmethod
    def get_or_create(cls, org, user, key: str, name: str):
        existing = org.globals.filter(key__iexact=key, is_active=True).first()
        if existing:
            return existing

        if not name:
            name = cls.get_unique_name(org, unsnakify(key))

        return cls.objects.create(org=org, key=key, name=name, value="", created_by=user, modified_by=user)

    @classmethod
    def name_to_key(cls, name: str) -> str:
        key = strip_non_ascii(name.lower())
        key = re.sub(r"\s+", "_", key)
        return re.sub(r"[^0-9a-zA-Z_-]", "", key)

    @classmethod
    def is_valid_key(cls, value: str) -> bool:
        try:
            KeyValidator(max_length=cls.MAX_KEY_LEN)(value)
            return True
        except ValidationError:
            return False

    @classmethod
    def annotate_usage(cls, queryset):
        return queryset.annotate(usage_count=Count("dependent_flows", distinct=True))

    def release(self, user):
        super().release(user)

        self.is_active = False
        self.name = self._deleted_name()
        self.modified_by = user
        self.save(update_fields=("is_active", "name", "modified_by", "modified_on"))
