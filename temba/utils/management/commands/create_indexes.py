import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from django.conf import settings
from django.core.management import BaseCommand, CommandError

MESSAGES_TEMPLATE_FILE = "temba/utils/management/commands/data/os_messages.json"


class Command(BaseCommand):
    help = "Creates OpenSearch index templates that don't already exist."

    def handle(self, *args, **kwargs):
        endpoint = settings.OPENSEARCH_MESSAGES_ENDPOINT
        if not endpoint:
            raise CommandError("OPENSEARCH_MESSAGES_ENDPOINT is not configured")

        endpoint = endpoint.rstrip("/")

        resp = self._signed_request("GET", f"{endpoint}/_index_template/messages-template")
        if resp.status_code == 200:
            self.stdout.write("Index template messages-template already exists")
            return

        with open(MESSAGES_TEMPLATE_FILE, "r") as f:
            body = f.read()

        resp = self._signed_request("PUT", f"{endpoint}/_index_template/messages-template", body=body)
        if resp.status_code not in (200, 201):
            raise CommandError(f"Failed to create index template: {resp.status_code} {resp.text}")

        self.stdout.write("Created index template messages-template")

    def _signed_request(self, method, url, body=None):
        """Makes a SigV4-signed request to AWS OpenSearch Serverless."""

        session = boto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        credentials = session.get_credentials().get_frozen_credentials()

        headers = {"Content-Type": "application/json"}
        aws_request = AWSRequest(method=method, url=url, data=body, headers=headers)
        service = "aoss" if ".aoss." in url else "es"

        SigV4Auth(credentials, service, settings.AWS_REGION).add_auth(aws_request)

        return requests.request(method=method, url=url, data=body, headers=dict(aws_request.headers))
