import json

import requests

from django.conf import settings
from django.core.management import BaseCommand, CommandError

MESSAGES_TEMPLATE_FILE = "temba/utils/management/commands/data/os_messages-tickets.json"
MESSAGES_TEMPLATE_NAME = "messages-tickets"


class Command(BaseCommand):
    help = "Creates OpenSearch index templates that don't already exist."

    def handle(self, *args, **kwargs):
        if not settings.OPENSEARCH_ENDPOINT_URL:
            raise CommandError("OPENSEARCH_ENDPOINT_URL must be configured")

        with open(MESSAGES_TEMPLATE_FILE, "r") as f:
            schema = json.load(f)

        self._create_template(MESSAGES_TEMPLATE_NAME, schema)

    def _create_template(self, name: str, schema: dict):
        """Creates an index template using the OpenSearch REST API."""

        endpoint = settings.OPENSEARCH_ENDPOINT_URL.rstrip("/")

        resp = requests.get(f"{endpoint}/_index_template/{name}")
        if resp.status_code == 200:
            self.stdout.write(f"Index template {name} already exists")
            return
        elif resp.status_code != 404:
            raise CommandError(f"Failed to check index template: {resp.status_code} {resp.text}")

        resp = requests.put(f"{endpoint}/_index_template/{name}", json=schema)
        if resp.status_code not in (200, 201):
            raise CommandError(f"Failed to create index template: {resp.status_code} {resp.text}")

        self.stdout.write(f"Created index template {name}")
