import logging
import time
import types
from abc import abstractmethod
from collections import OrderedDict

from smartmin.models import SmartModel

from django.contrib.postgres.fields import HStoreField
from django.core import checks
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.db.models import JSONField as DjangoJSONField, Sum
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from . import json, uuid
from .fields import NameValidator

logger = logging.getLogger(__name__)


def generate_uuid():
    """
    Returns a random stringified UUID for use with older models that use char fields instead of UUID fields
    """
    return str(uuid.uuid4())


def patch_queryset_count(qs, function):
    """
    As of Django 2.2 a patched .count on querysets has to look like a real method
    """
    qs.count = types.MethodType(lambda s: function(), qs)


class IDSliceQuerySet(models.query.RawQuerySet):
    """
    QuerySet defined by a model, set of ids, offset and total count
    """

    def __init__(self, model, ids, *, offset, total, only=None, using="default", _raw_query=None):
        if _raw_query:
            # we're being cloned so can reuse our SQL query
            raw_query = _raw_query
        else:
            cols = ", ".join([f"t.{f}" for f in only]) if only else "t.*"
            table = model._meta.db_table

            if len(ids) > 0:
                # build a list of sequence to model id, so we can sort by the sequence in our results
                pairs = ", ".join(str((seq, model_id)) for seq, model_id in enumerate(ids, start=1))

                raw_query = f"""SELECT {cols} FROM {table} t JOIN (VALUES {pairs}) tmp_resultset (seq, model_id) ON t.id = tmp_resultset.model_id ORDER BY tmp_resultset.seq"""
            else:
                raw_query = f"""SELECT {cols} FROM {table} t WHERE t.id < 0"""

        super().__init__(raw_query, model, using=using)

        self.ids = ids
        self.offset = offset
        self.total = total

    def __getitem__(self, k):
        """
        Called to slice our queryset. ID Slice Query Sets care created pre-sliced, that is the offset and counts should
        match the way any kind of paginator is going to try to slice the queryset.
        """
        if isinstance(k, int):
            # single item
            if k < self.offset or k >= self.offset + len(self.ids):
                raise IndexError("attempt to access element outside slice")

            return super().__getitem__(k - self.offset)

        elif isinstance(k, slice):
            start = k.start if k.start else 0
            if start != self.offset:
                raise IndexError(
                    f"attempt to slice ID queryset with differing offset: [{k.start}:{k.stop}] != [{self.offset}:{self.offset+len(self.ids)}]"
                )

            return list(self)[: k.stop - self.offset]

        else:
            raise TypeError(f"__getitem__ index must be int, not {type(k)}")

    def all(self):
        return self

    def none(self):
        return IDSliceQuerySet(self.model, [], offset=0, total=0, using=self._db)

    def count(self):
        return self.total

    def filter(self, **kwargs):
        ids = list(self.ids)

        for k, v in kwargs.items():
            if k == "pk":
                ids = [i for i in ids if i == int(v)]
            elif k == "pk__in":
                v = {int(j) for j in v}  # django forms like passing around pks as strings
                ids = [i for i in ids if i in v]
            else:
                raise ValueError(f"IDSliceQuerySet instances can only be filtered by pk, not {k}")

        return IDSliceQuerySet(self.model, ids, offset=0, total=len(ids), using=self._db)

    def _clone(self):
        return self.__class__(
            self.model, self.ids, offset=self.offset, total=self.total, using=self._db, _raw_query=self.raw_query
        )


def mapEStoDB(model, es_queryset, only_ids=False):  # pragma: no cover
    """
    Map ElasticSearch results to Django Model objects
    We use object PKs from ElasticSearch result set and select those objects in the database
    """
    pks = (result.id for result in es_queryset)

    if only_ids:
        return pks
    else:
        # prepare the data set
        pairs = ",".join(str((seq, model_id)) for seq, model_id in enumerate(pks, start=1))

        if pairs:
            return model.objects.raw(
                f"""SELECT model.*
                from {model._meta.db_table} AS model JOIN (VALUES {pairs}) tmp_resultset (seq, model_id)
                    ON model.id = tmp_resultset.model_id
                ORDER BY tmp_resultset.seq
                """
            )
        else:  # pragma: no cover
            return model.objects.none()


class TranslatableField(HStoreField):
    """
    Model field which is a set of language code and translation pairs stored as HSTORE
    """

    class Validator:
        def __init__(self, max_length):
            self.max_length = max_length

        def __call__(self, value):
            for lang, translation in value.items():
                if lang != "base" and len(lang) != 3:
                    raise ValidationError("'%s' is not a valid language code." % lang)
                if len(translation) > self.max_length:
                    raise ValidationError(
                        "Translation for '%s' exceeds the %d character limit." % (lang, self.max_length)
                    )

    def __init__(self, max_length, **kwargs):
        super().__init__(**kwargs)

        self.max_length = max_length

    @cached_property
    def validators(self):
        return super().validators + [TranslatableField.Validator(self.max_length)]


class CheckFieldDefaultMixin:
    """
    This was copied from https://github.com/django/django/commit/f6e1789654e82bac08cead5a2d2a9132f6403f52

    More info: https://code.djangoproject.com/ticket/28577
    """

    _default_hint = ("<valid default>", "<invalid default>")

    def _check_default(self):
        if self.has_default() and self.default is not None and not callable(self.default):
            return [
                checks.Warning(
                    "%s default should be a callable instead of an instance so that it's not shared between all field "
                    "instances." % (self.__class__.__name__,),
                    hint="Use a callable instead, e.g., use `%s` instead of `%s`." % self._default_hint,
                    obj=self,
                    id="postgres.E003",
                )
            ]
        else:
            return []

    def check(self, **kwargs):
        errors = super().check(**kwargs)
        errors.extend(self._check_default())
        return errors


class JSONAsTextField(CheckFieldDefaultMixin, models.Field):
    """
    Custom JSON field that is stored as Text in the database

    Notes:
        * uses standard JSON serializers so it expects that all data is a valid JSON data
        * be careful with default values, it must be a callable returning a dict because using `default={}` will create
          a mutable default that is share between all instances of the JSONAsTextField
          https://docs.djangoproject.com/en/1.11/ref/contrib/postgres/fields/#jsonfield
    """

    description = "Custom JSON field that is stored as Text in the database"
    _default_hint = ("dict", "{}")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, *args, **kwargs):
        if self.has_default() and value is None:
            return self.get_default()

        if value is None:
            return value

        if isinstance(value, str):
            data = json.loads(value)

            if type(data) not in (list, dict, OrderedDict):
                raise ValueError("JSONAsTextField should be a dict or a list, got %s => %s" % (type(data), data))
            else:
                return data
        else:
            raise ValueError('Unexpected type "%s" for JSONAsTextField' % (type(value),))

    def get_db_prep_value(self, value, *args, **kwargs):
        # if the value is falsy we will save is as null
        if self.null and value in (None, {}, []) and not kwargs.get("force"):
            return None

        if value is None:
            return None

        if type(value) not in (list, dict, OrderedDict):
            raise ValueError("JSONAsTextField should be a dict or a list, got %s => %s" % (type(value), value))

        serialized = json.dumps(value)

        # strip out unicode sequences which aren't valid in JSONB
        return serialized.replace("\\u0000", "")

    def to_python(self, value):
        if isinstance(value, str):
            value = json.loads(value)
        return value

    def db_type(self, connection):
        return "text"

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, path, args, kwargs


class JSONField(DjangoJSONField):
    """
    Convenience subclass of the regular JSONField that uses our custom JSON encoder
    """

    def __init__(self, *args, **kwargs):
        kwargs["encoder"] = json.TembaEncoder
        kwargs["decoder"] = json.TembaDecoder
        super().__init__(*args, **kwargs)


class SquashableModel(models.Model):
    """
    Base class for models which track counts by delta insertions which are then periodically squashed
    """

    squash_over = ()

    id = models.BigAutoField(auto_created=True, primary_key=True)
    is_squashed = models.BooleanField(default=False)

    @classmethod
    def get_unsquashed(cls):
        return cls.objects.filter(is_squashed=False)

    @classmethod
    def squash(cls):
        start = time.time()
        num_sets = 0

        for distinct_set in cls.get_unsquashed().order_by(*cls.squash_over).distinct(*cls.squash_over)[:5000]:
            with connection.cursor() as cursor:
                sql, params = cls.get_squash_query(distinct_set)

                cursor.execute(sql, params)

            num_sets += 1

        time_taken = time.time() - start

        logging.debug("Squashed %d distinct sets of %s in %0.3fs" % (num_sets, cls.__name__, time_taken))

    @classmethod
    @abstractmethod
    def get_squash_query(cls, distinct_set) -> tuple:  # pragma: no cover
        pass

    @classmethod
    def sum(cls, instances) -> int:
        count_sum = instances.aggregate(count_sum=Sum("count"))["count_sum"]
        return count_sum if count_sum else 0

    class Meta:
        abstract = True


class ScopedCountModel(SquashableModel):
    """
    Base for scoped count squashable models
    """

    SQUASH_OVER = ("count_type", "scope")

    count_type = models.CharField(max_length=1)
    scope = models.CharField(max_length=32)
    count = models.IntegerField()

    @classmethod
    def get_squash_query(cls, distinct_set):  # pragma: no cover
        sql = f"""
        WITH removed as (
            DELETE FROM {cls._meta.db_table} WHERE count_type = %s AND scope = %s RETURNING count
        )
        INSERT INTO {cls._meta.db_table}(count_type, scope, count, is_squashed)
        VALUES (%s, %s, GREATEST(0, (SELECT SUM(count) FROM removed)), TRUE);
        """

        return sql, (distinct_set.count_type, distinct_set.scope)

    class CountSet:
        """
        A queryset of counts which can be aggregated in different ways
        """

        def __init__(self, counts, scopes):
            self.counts = counts
            self.scopes = scopes

        def total(self):
            """
            Calculates the overall total over a set of counts
            """
            total = self.counts.aggregate(total=Sum("count"))
            return total["total"] if total["total"] is not None else 0

        def scope_totals(self):
            """
            Calculates per-scope totals over a set of counts
            """
            totals = list(self.counts.values_list("scope").annotate(replies=Sum("count")))
            total_by_encoded_scope = {t[0]: t[1] for t in totals}

            total_by_scope = {}
            for encoded_scope, scope in self.scopes.items():
                total_by_scope[scope] = total_by_encoded_scope.get(encoded_scope, 0)

            return total_by_scope

    class Meta:
        abstract = True


class DailyCountModel(ScopedCountModel):
    """
    Base for daily scoped count squashable models
    """

    SQUASH_OVER = ("count_type", "scope", "day")

    day = models.DateField()

    @classmethod
    def get_squash_query(cls, distinct_set):
        sql = f"""
        WITH removed as (
            DELETE FROM {cls._meta.db_table} WHERE count_type = %s AND scope = %s AND day = %s RETURNING count
        )
        INSERT INTO {cls._meta.db_table}(count_type, scope, day, count, is_squashed)
        VALUES (%s, %s, %s, GREATEST(0, (SELECT SUM(count) FROM removed)), TRUE);
        """

        return sql, (distinct_set.count_type, distinct_set.scope, distinct_set.day) * 2

    @classmethod
    def _get_count_set(cls, count_type: str, scopes: dict, since, until):
        counts = cls.objects.filter(count_type=count_type, scope__in=scopes.keys())
        if since:
            counts = counts.filter(day__gte=since)
        if until:
            counts = counts.filter(day__lt=until)
        return DailyCountModel.CountSet(counts, scopes)

    class CountSet(ScopedCountModel.CountSet):
        """
        A queryset of counts which can be aggregated in different ways
        """

        def day_totals(self):
            """
            Calculates per-day totals over a set of counts
            """
            return list(self.counts.values_list("day").annotate(total=Sum("count")).order_by("day"))

        def month_totals(self):
            """
            Calculates per-month totals over a set of counts
            """
            counts = self.counts.extra(select={"month": 'EXTRACT(month FROM "day")'})
            return list(counts.values_list("month").annotate(replies=Sum("count")).order_by("month"))

    class Meta:
        abstract = True


class LegacyUUIDMixin(SmartModel):
    """
    Model mixin for things with an old-style VARCHAR(36) UUID
    """

    uuid = models.CharField(
        max_length=36,
        unique=True,
        db_index=True,
        default=generate_uuid,
        verbose_name=_("Unique Identifier"),
        help_text=_("The unique identifier for this object"),
    )

    class Meta:
        abstract = True


class TembaUUIDMixin(models.Model):
    """
    Model mixin for things with a UUID
    """

    uuid = models.UUIDField(unique=True, default=uuid.uuid4)

    class Meta:
        abstract = True


class TembaNameMixin(models.Model):
    """
    Model mixin for things with a name
    """

    MAX_NAME_LEN = 64

    name = models.CharField(max_length=MAX_NAME_LEN, validators=[NameValidator(MAX_NAME_LEN)])

    @classmethod
    def get_unique_name(cls, org, base_name: str, ignore=None) -> str:
        """
        Generates a unique name from the given base name that won't conflict with any named object in the given queryset
        """
        qs = cls.objects.filter(org=org, is_active=True)
        if ignore:
            qs = qs.exclude(id=ignore.id)

        count = 1
        while True:
            count_str = f" {count}"
            name = f"{base_name[:cls.MAX_NAME_LEN - len(count_str)]}{count_str}" if count > 1 else base_name
            if not qs.filter(name__iexact=name).exists():
                return name
            count += 1

    @classmethod
    def is_valid_name(cls, value: str) -> bool:
        try:
            NameValidator(max_length=cls.MAX_NAME_LEN)(value)
            return True
        except ValidationError:
            return False

    @classmethod
    def clean_name(cls, original: str) -> str:
        """
        Cleans a name from an import to try to make it valid
        """
        return original.strip()[: cls.MAX_NAME_LEN].replace('"', "'").replace("\\", "/").replace("\0", "")

    def deleted_name(self) -> str:
        return f"deleted-{uuid.uuid4()}-{self.name}"[: self.MAX_NAME_LEN]

    class Meta:
        abstract = True


class TembaModel(TembaUUIDMixin, TembaNameMixin, SmartModel):
    """
    Base for models which have UUID, name and smartmin auditing fields
    """

    def as_export_ref(self) -> dict:
        return {"uuid": str(self.uuid), "name": self.name}

    def __str__(self):
        """
        How widgets will render this object
        """
        return self.name

    def __repr__(self):
        """
        How the shell will render this object
        """
        return f'<{self.__class__.__name__}: uuid={self.uuid} name="{self.name}">'

    class Meta:
        abstract = True
