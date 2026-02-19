import json

import boto3
import requests
from botocore.exceptions import ClientError

from django.conf import settings
from django.core.management import BaseCommand, CommandError

MESSAGES_INDEX_FILE = "temba/utils/management/commands/data/os_messages.json"


class Command(BaseCommand):
    help = "Creates OpenSearch indexes that don't already exist."

    def handle(self, *args, **kwargs):
        with open(MESSAGES_INDEX_FILE, "r") as f:
            schema = json.load(f)

        if settings.OPENSEARCH_MESSAGES_COLLECTION_ID:
            self._create_serverless(schema)
        elif settings.OPENSEARCH_ENDPOINT_URL:
            self._create_local(schema)
        else:
            raise CommandError("OPENSEARCH_MESSAGES_COLLECTION_ID or OPENSEARCH_ENDPOINT_URL must be configured")

    def _create_serverless(self, schema: dict):
        """Creates the index using the AWS OpenSearch Serverless API."""

        client = boto3.client(
            "opensearchserverless",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )

        try:
            client.create_index(id=settings.OPENSEARCH_MESSAGES_COLLECTION_ID, indexName="messages", indexSchema=schema)
        except client.exceptions.ConflictException:
            self.stdout.write("Index messages already exists")
            return
        except ClientError as e:
            raise CommandError(f"Failed to create index: {e}")

        self.stdout.write("Created index messages")

    def _create_local(self, schema: dict):
        """Creates the index using the OpenSearch REST API."""

        endpoint = settings.OPENSEARCH_ENDPOINT_URL.rstrip("/")

        resp = requests.head(f"{endpoint}/messages")
        if resp.status_code == 200:
            self.stdout.write("Index messages already exists")
            return
        elif resp.status_code != 404:
            raise CommandError(f"Failed to check index: {resp.status_code} {resp.text}")

        resp = requests.put(f"{endpoint}/messages", json=schema)
        if resp.status_code not in (200, 201):
            raise CommandError(f"Failed to create index: {resp.status_code} {resp.text}")

        self.stdout.write("Created index messages")
