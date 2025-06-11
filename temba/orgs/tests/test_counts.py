from datetime import date

from temba.orgs.tasks import squash_item_counts
from temba.tests import TembaTest


class ItemCountTest(TembaTest):
    def test_model(self):
        self.org.counts.create(scope="foo:1", count=2)
        self.org.counts.create(scope="foo:1", count=3)
        self.org.counts.create(scope="foo:2", count=1)
        self.org.counts.create(scope="foo:3", count=4)
        self.org2.counts.create(scope="foo:4", count=1)
        self.org2.counts.create(scope="foo:4", count=1)

        self.assertEqual(9, self.org.counts.filter(scope__in=("foo:1", "foo:3")).sum())
        self.assertEqual(10, self.org.counts.prefix("foo:").sum())
        self.assertEqual(10, self.org.counts.prefix(["foo:"]).sum())
        self.assertEqual(0, self.org.counts.prefix([]).sum())
        self.assertEqual(4, self.org.counts.count())

        squash_item_counts()

        self.assertEqual(9, self.org.counts.filter(scope__in=("foo:1", "foo:3")).sum())
        self.assertEqual(10, self.org.counts.prefix("foo:").sum())
        self.assertEqual(3, self.org.counts.count())

        self.org.counts.all().delete()


class DailyCountTest(TembaTest):
    def test_model(self):
        self.org.daily_counts.create(day=date(2025, 3, 20), scope="foo:a", count=2)
        self.org.daily_counts.create(day=date(2025, 3, 20), scope="foo:a", count=3)
        self.org.daily_counts.create(day=date(2025, 3, 20), scope="foo:b", count=1)
        self.org.daily_counts.create(day=date(2025, 4, 5), scope="foo:a", count=1)
        self.org.daily_counts.create(day=date(2025, 4, 15), scope="foo:a", count=1)
        self.org.daily_counts.create(day=date(2025, 4, 15), scope="foo:a", count=6)
        self.org.daily_counts.create(day=date(2025, 4, 15), scope="foo:b", count=2)
        self.org2.daily_counts.create(day=date(2025, 4, 15), scope="foo:a", count=1)

        self.assertEqual(13, self.org.daily_counts.filter(scope="foo:a").sum())
        self.assertEqual(16, self.org.daily_counts.prefix("foo:").sum())
        self.assertEqual(
            {
                (date(2025, 3, 20), "foo:a"): 5,
                (date(2025, 3, 20), "foo:b"): 1,
                (date(2025, 4, 5), "foo:a"): 1,
                (date(2025, 4, 15), "foo:a"): 7,
                (date(2025, 4, 15), "foo:b"): 2,
            },
            self.org.daily_counts.prefix("foo:").day_totals(scoped=True),
        )
        self.assertEqual(
            {date(2025, 3, 20): 6, date(2025, 4, 5): 1, date(2025, 4, 15): 9},
            self.org.daily_counts.prefix("foo:").day_totals(scoped=False),
        )
        self.assertEqual(
            {date(2025, 3, 20): 6, date(2025, 4, 5): 1},
            self.org.daily_counts.period(date(2025, 3, 1), date(2025, 4, 10)).day_totals(scoped=False),
        )
        self.assertEqual(
            {
                (date(2025, 3, 1), "foo:a"): 5,
                (date(2025, 3, 1), "foo:b"): 1,
                (date(2025, 4, 1), "foo:a"): 8,
                (date(2025, 4, 1), "foo:b"): 2,
            },
            self.org.daily_counts.prefix("foo:").month_totals(scoped=True),
        )
        self.assertEqual(
            {date(2025, 3, 1): 6, date(2025, 4, 1): 10},
            self.org.daily_counts.prefix("foo:").month_totals(scoped=False),
        )
        self.assertEqual(7, self.org.daily_counts.count())

        squash_item_counts()

        self.assertEqual(13, self.org.daily_counts.filter(scope="foo:a").sum())
        self.assertEqual(16, self.org.daily_counts.prefix("foo:").sum())
        self.assertEqual(5, self.org.daily_counts.count())

        self.org.daily_counts.all().delete()
