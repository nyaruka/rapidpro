from botocore.exceptions import ClientError

from django.conf import settings
from django.core.management import BaseCommand

from temba.utils import dynamo

TABLES = [
    {
        "TableName": "Main",
        "KeySchema": [
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        "TimeToLiveSpecification": {"AttributeName": "TTL", "Enabled": True},
        "TableClass": "STANDARD",
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "History",
        "KeySchema": [
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        "TimeToLiveSpecification": {"AttributeName": "TTL", "Enabled": True},
        "TableClass": "STANDARD_INFREQUENT_ACCESS",
        "BillingMode": "PAY_PER_REQUEST",
    },
]


class Command(BaseCommand):
    help = "Creates DynamoDB tables that don't already exist."

    def add_arguments(self, parser):
        parser.add_argument("--testing", action="store_true")

    def handle(self, testing: bool, *args, **kwargs):
        self.client = dynamo.get_client()

        # during tests settings.TESTING is true so table prefix is "Test" - but this command is run with
        # settings.TESTING == False, so when setting up tables for testing we need to override the prefix
        if testing:
            settings.DYNAMO_TABLE_PREFIX = "Test"

        for table in TABLES:
            self._migrate_table(table)

    def _migrate_table(self, table: dict):
        name = table["TableName"]
        real_name = settings.DYNAMO_TABLE_PREFIX + name

        if not self._table_exists(real_name):
            spec = table.copy()
            spec["TableName"] = real_name

            # invoke pre-create signal to allow for table modifications
            dynamo.signals.pre_create_table.send(self.__class__, spec=spec)

            # ttl isn't actually part of the create call
            ttlSpec = spec.pop("TimeToLiveSpecification", None)

            self.stdout.write(f"Creating {real_name}...", ending="")
            self.stdout.flush()

            table = self.client.create_table(**spec)
            table.wait_until_exists()

            self.stdout.write(self.style.SUCCESS(" OK"))

            if ttlSpec:
                self.client.meta.client.update_time_to_live(TableName=real_name, TimeToLiveSpecification=ttlSpec)

                self.stdout.write(f"Updated TTL for {real_name}")
        else:
            self.stdout.write(f"Skipping {real_name} which already exists")

    def _table_exists(self, real_name: str) -> bool:
        """
        Returns whether the given table exists.
        """

        try:
            self.client.Table(real_name).table_status
            return True
        except ClientError:
            return False
