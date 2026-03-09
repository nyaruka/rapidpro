import json

from django.conf import settings
from django.core.management import BaseCommand, CommandError

from temba.utils.osearch import get_client

MESSAGES_TEMPLATE_FILE = "temba/utils/management/commands/data/os_messages.json"
MESSAGES_TEMPLATE_NAME = "messages-v1"

CONTACTS_INDEX_FILE = "temba/utils/management/commands/data/os_contacts.json"
CONTACTS_INDEX_NAME = "contacts-v1"
CONTACTS_INDEX_ALIAS = "contacts"


class Command(BaseCommand):
    help = "Creates OpenSearch indices or templates."

    def add_arguments(self, parser):
        parser.add_argument("index", choices=["messages", "contacts"], help="Index to create")
        parser.add_argument(
            "--shards", type=int, choices=range(1, 11), help="Override number of shards (1-10)", default=None
        )
        parser.add_argument(
            "--replicas", type=int, choices=range(0, 3), help="Override number of replicas (0-2)", default=None
        )

    def handle(self, index: str, shards: int, replicas: int, *args, **options):
        if not settings.OPENSEARCH_ENDPOINT_URL:
            raise CommandError("OPENSEARCH_ENDPOINT_URL must be configured")

        client = get_client()

        if index == "messages":
            with open(MESSAGES_TEMPLATE_FILE, "r") as f:
                schema = json.load(f)

            if shards is not None:
                schema["template"]["settings"]["index"]["number_of_shards"] = shards
            if replicas is not None:
                schema["template"]["settings"]["index"]["number_of_replicas"] = replicas

            self._create_template(client, MESSAGES_TEMPLATE_NAME, schema)

        elif index == "contacts":
            with open(CONTACTS_INDEX_FILE, "r") as f:
                schema = json.load(f)

            if shards is not None:
                schema["settings"]["index"]["number_of_shards"] = shards
            if replicas is not None:
                schema["settings"]["index"]["number_of_replicas"] = replicas

            self._create_index(client, CONTACTS_INDEX_NAME, schema, alias=CONTACTS_INDEX_ALIAS)

    def _create_template(self, client, name: str, schema: dict):
        """Creates an index template using the OpenSearch API."""

        client.indices.put_index_template(name, body=schema)

        opts = schema["template"]["settings"]["index"]
        self.stdout.write(
            f"Put {name} index template (shards={opts['number_of_shards']}, replicas={opts['number_of_replicas']})"
        )

    def _create_index(self, client, name: str, schema: dict, alias: str = ""):
        """Creates a regular index using the OpenSearch API."""

        client.indices.create(index=name, body=schema)

        opts = schema["settings"]["index"]
        self.stdout.write(
            f"Created {name} index (shards={opts['number_of_shards']}, replicas={opts['number_of_replicas']})"
        )

        if alias:
            client.indices.put_alias(index=name, name=alias)
            self.stdout.write(f"Added alias {alias} -> {name}")
