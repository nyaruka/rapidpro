import json
from urllib.parse import urlparse

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

from django.conf import settings
from django.core.management import BaseCommand, CommandError

MESSAGES_TEMPLATE_FILE = "temba/utils/management/commands/data/os_messages.json"
MESSAGES_TEMPLATE_NAME = "messages-v1"


class Command(BaseCommand):
    help = "Creates OpenSearch indices or templates that don't already exist."

    def add_arguments(self, parser):
        parser.add_argument(
            "--shards", type=int, choices=range(1, 11), help="Override number of shards (1-10)", default=None
        )
        parser.add_argument(
            "--replicas", type=int, choices=range(0, 3), help="Override number of replicas (0-2)", default=None
        )

    def handle(self, shards: int, replicas: int, *args, **options):
        if not settings.OPENSEARCH_ENDPOINT_URL:
            raise CommandError("OPENSEARCH_ENDPOINT_URL must be configured")

        client = self._get_client()

        with open(MESSAGES_TEMPLATE_FILE, "r") as f:
            schema = json.load(f)

        if shards is not None:
            schema["template"]["settings"]["index"]["number_of_shards"] = shards
        if replicas is not None:
            schema["template"]["settings"]["index"]["number_of_replicas"] = replicas

        self._create_template(client, MESSAGES_TEMPLATE_NAME, schema)

    def _create_template(self, client: OpenSearch, name: str, schema: dict):
        """Creates an index template using the OpenSearch API."""

        if client.indices.exists_index_template(name):
            self.stdout.write(f"Index template {name} already exists")
            return

        client.indices.put_index_template(name, body=schema)
        self.stdout.write(f"Created index template {name}")

    def _get_client(self) -> OpenSearch:
        parsed = urlparse(settings.OPENSEARCH_ENDPOINT_URL)
        use_ssl = parsed.scheme == "https"

        kwargs = {}
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            session = boto3.Session(
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
            )
            kwargs["http_auth"] = AWSV4SignerAuth(session.get_credentials(), settings.AWS_REGION, service="es")

        return OpenSearch(
            hosts=[{"host": parsed.hostname, "port": parsed.port or (443 if use_ssl else 9200)}],
            use_ssl=use_ssl,
            verify_certs=use_ssl,
            connection_class=RequestsHttpConnection,
            **kwargs,
        )
