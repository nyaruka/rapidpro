from datetime import date

from django.db import connection, models
from django.db.models import Q, Sum

from temba.utils.db.queries import or_list


class CountQuerySet(models.QuerySet):
    """
    Custom queryset for count models.
    """

    def sum(self) -> int:
        """
        Sums counts over the matching rows.
        """
        return self.aggregate(count_sum=Sum("count"))["count_sum"] or 0


class BaseSquashableCount(models.Model):
    """
    Base class for models which track counts by delta insertions which are then periodically squashed.
    """

    squash_over = ()
    squash_max_distinct = 5000

    id = models.BigAutoField(auto_created=True, primary_key=True)
    count = models.IntegerField()
    is_squashed = models.BooleanField(default=False)

    objects = CountQuerySet.as_manager()

    @classmethod
    def get_squash_over(cls) -> tuple:
        return cls.squash_over

    @classmethod
    def get_unsquashed(cls):
        return cls.objects.filter(is_squashed=False)

    @classmethod
    def squash(cls) -> int:
        """
        Squashes all distinct sets of counts with unsquashed rows into a single row if they sum to non-zero or just
        deletes them if they sum to zero. Returns the number of sets squashed.
        """

        num_sets = 0
        squash_over = cls.get_squash_over()
        distinct_sets = (
            cls.get_unsquashed()
            .values(*squash_over)
            .order_by(*squash_over)
            .distinct(*squash_over)[: cls.squash_max_distinct]
        )

        for distinct_set in distinct_sets:
            with connection.cursor() as cursor:
                sql, params = cls.get_squash_query(distinct_set)

                cursor.execute(sql, params)

            num_sets += 1

        return num_sets

    @classmethod
    def get_squash_query(cls, distinct_set: dict) -> tuple:
        squash_over = cls.get_squash_over()
        delete_cond = " AND ".join([f'"{col}" = %s' for col in squash_over])
        insert_cols = ", ".join([f'"{col}"' for col in squash_over])
        insert_vals = ", ".join(["%s"] * len(squash_over))

        sql = f"""
        WITH removed as (
            DELETE FROM {cls._meta.db_table} WHERE {delete_cond} RETURNING "count"
        )
        INSERT INTO {cls._meta.db_table}({insert_cols}, "count", "is_squashed")
        SELECT {insert_vals}, s.total, TRUE FROM (
            SELECT COALESCE(SUM("count"), 0) AS "total" FROM removed
        ) s WHERE s.total != 0;
        """

        return sql, tuple(distinct_set[col] for col in squash_over) * 2

    class Meta:
        abstract = True


class ScopedCountQuerySet(CountQuerySet):
    """
    Specialized queryset for scope + count models.
    """

    def prefix(self, match: list | str):
        """
        Filters by the given scope prefix or list of prefixes.
        """
        if isinstance(match, list):
            if match:
                return self.filter(or_list([Q(scope__startswith=p) for p in match]))
            else:
                return self.none()

        return self.filter(scope__startswith=match)

    def scope_totals(self) -> dict[str, int]:
        """
        Sums counts grouped by scope.
        """
        counts = self.values_list("scope").annotate(count_sum=Sum("count"))
        return {c[0]: c[1] for c in counts}


class BaseScopedCount(BaseSquashableCount):
    """
    Base class for count models which have scope field.
    """

    scope = models.CharField(max_length=128)

    objects = ScopedCountQuerySet.as_manager()

    class Meta:
        abstract = True


class DailyCountQuerySet(ScopedCountQuerySet):
    """
    Specialized queryset for scope + day + count models.
    """

    def period(self, since, until):
        return self.filter(day__gte=since, day__lt=until)

    def day_totals(self, *, scoped: bool) -> dict[date | tuple, int]:
        """
        Sums counts grouped by day or day + scope.
        """
        if scoped:
            counts = self.values_list("day", "scope").annotate(count_sum=Sum("count"))
            return {(c[0], c[1]): c[2] for c in counts}
        else:
            counts = self.values_list("day").annotate(count_sum=Sum("count"))
            return {c[0]: c[1] for c in counts}

    def month_totals(self, *, scoped: bool) -> dict[date | tuple, int]:
        """
        Sums counts grouped by month or month + scope.
        """

        with_month = self.extra({"month": "date_trunc('month', day)::date"})

        if scoped:
            counts = with_month.values_list("month", "scope").annotate(count_sum=Sum("count"))
            return {(c[0], c[1]): c[2] for c in counts}
        else:
            counts = with_month.values_list("month").annotate(count_sum=Sum("count"))
            return {c[0]: c[1] for c in counts}


class BaseDailyCount(BaseScopedCount):
    """
    Base class for count models which have scope and day field.
    """

    day = models.DateField()

    objects = DailyCountQuerySet.as_manager()

    class Meta:
        abstract = True
