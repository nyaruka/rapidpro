from io import StringIO

from django.core.management import call_command
from django.test.utils import override_settings

from temba.tests import TembaTest
from temba.utils import dynamo, s3

from .create_buckets import BUCKETS


class CreateBucketsTest(TembaTest):
    def tearDown(self):
        client = s3.client()

        for bucket in BUCKETS:
            client.delete_bucket(Bucket=f"temp-{bucket}")

        return super().tearDown()

    @override_settings(BUCKET_PREFIX="temp")
    def test_create_buckets(self):
        out = StringIO()
        call_command("create_buckets", stdout=out)

        self.assertIn("created bucket temp-archives", out.getvalue())
        self.assertIn("created bucket temp-default", out.getvalue())

        print(out.getvalue())

        out = StringIO()
        call_command("create_buckets", stdout=out)

        print(out.getvalue())

        self.assertIn("Bucket temp-archives already exists", out.getvalue())
        self.assertIn("Bucket temp-default already exists", out.getvalue())


class MigrateDynamoTest(TembaTest):
    def tearDown(self):
        client = dynamo.get_client()

        for table in client.tables.all():
            if table.name.startswith("Temp"):
                table.delete()

        return super().tearDown()

    @override_settings(DYNAMO_TABLE_PREFIX="Temp")
    def test_migrate_dynamo(self):
        def pre_create_table(sender, spec, **kwargs):
            spec["Tags"] = [{"Key": "Foo", "Value": "Bar"}]

        dynamo.signals.pre_create_table.connect(pre_create_table)

        out = StringIO()
        call_command("migrate_dynamo", stdout=out)

        self.assertIn("Creating TempMain", out.getvalue())
        self.assertIn("Creating TempHistory", out.getvalue())

        client = dynamo.get_client()
        table = client.Table("TempMain")
        self.assertEqual("ACTIVE", table.table_status)

        out = StringIO()
        call_command("migrate_dynamo", stdout=out)

        self.assertIn("Skipping TempMain", out.getvalue())
        self.assertIn("Skipping TempHistory", out.getvalue())
