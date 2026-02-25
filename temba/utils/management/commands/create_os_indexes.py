import json
from urllib.parse import urlparse

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

from django.conf import settings
from django.core.management import BaseCommand, CommandError

MESSAGES_TEMPLATE_FILE = "temba/utils/management/commands/data/os_messages-tickets.json"
MESSAGES_TEMPLATE_NAME = "messages-tickets"


class Command(BaseCommand):
    help = "Creates OpenSearch index templates that don't already exist."

    def handle(self, *args, **kwargs):
        if not settings.OPENSEARCH_ENDPOINT_URL:
            raise CommandError("OPENSEARCH_ENDPOINT_URL must be configured")

        client = self._get_client()

        with open(MESSAGES_TEMPLATE_FILE, "r") as f:
            schema = json.load(f)

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
