import regex

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from temba.orgs.models import DependencyMixin, Org
from temba.utils.models import TembaModel
from temba.utils.text import unsnakify


class Global(TembaModel, DependencyMixin):
    """
    A global is a constant value that can be used in templates in flows and messages.
    """

    MAX_KEY_LEN = 36
    MAX_NAME_LEN = 36
    MAX_VALUE_LEN = settings.GLOBAL_VALUE_SIZE

    org = models.ForeignKey(Org, related_name="globals", on_delete=models.PROTECT)
    key = models.CharField(verbose_name=_("Key"), max_length=MAX_KEY_LEN)
    name = models.CharField(verbose_name=_("Name"), max_length=MAX_NAME_LEN)
    value = models.TextField(max_length=MAX_VALUE_LEN)

    org_limit_key = Org.LIMIT_GLOBALS

    @classmethod
    def get_or_create(cls, org, user, key, name, value):
        existing = org.globals.filter(key__iexact=key, is_active=True).first()
        if existing:
            if value:
                existing.value = value
                existing.modified_by = user
                existing.save(update_fields=("value", "modified_by"))
            return existing

        if not name:
            name = unsnakify(key)

        return cls.objects.create(org=org, key=key, name=name, value=value, created_by=user, modified_by=user)

    @classmethod
    def make_key(cls, name):
        """
        Generates a key from a name. There is no guarantee that the key is valid so should be checked with is_valid_key
        """
        key = regex.sub(r"([^a-z0-9]+)", " ", name.lower(), regex.V0)
        return regex.sub(r"([^a-z0-9]+)", "_", key.strip(), regex.V0)

    @classmethod
    def is_valid_key(cls, key):
        return regex.match(r"^[a-z][a-z0-9_]*$", key, regex.V0) and len(key) <= cls.MAX_KEY_LEN

    @classmethod
    def is_valid_name(cls, name):
        return regex.match(r"^[A-Za-z0-9_\- ]+$", name, regex.V0) and len(name) <= cls.MAX_NAME_LEN

    def release(self, user):
        super().release(user)

        self.is_active = False
        self.name = self._deleted_name()
        self.modified_by = user
        self.save(update_fields=("is_active", "name", "modified_by", "modified_on"))
