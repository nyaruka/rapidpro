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
        self.assertEqual(4, self.org.counts.count())

        squash_item_counts()

        self.assertEqual(9, self.org.counts.filter(scope__in=("foo:1", "foo:3")).sum())
        self.assertEqual(10, self.org.counts.prefix("foo:").sum())
        self.assertEqual(3, self.org.counts.count())

        self.org.counts.all().delete()
