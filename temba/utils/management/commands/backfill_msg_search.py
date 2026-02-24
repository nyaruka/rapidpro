from urllib.parse import urlparse

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection, helpers

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db.models.functions import Length

from temba.msgs.models import Msg

MESSAGES_INDEX_NAME = "messages-tickets-v1"
BATCH_SIZE = 500


class Command(BaseCommand):
    help = "Backfills messages from the database into the OpenSearch messages index."

    def add_arguments(self, parser):
        parser.add_argument("start_uuid", help="UUID of the message to start from (works backwards from here)")

    def handle(self, start_uuid: str, *args, **options):
        os_client = self._get_os_client()

        try:
            start_msg = Msg.objects.get(uuid=start_uuid)
        except Msg.DoesNotExist:
            raise CommandError(f"Message with UUID {start_uuid} not found")

        queryset = (
            Msg.objects.annotate(text_len=Length("text"))
            .filter(
                ticket_uuid__isnull=False,
                text_len__gte=2,
                visibility__in=(Msg.VISIBILITY_VISIBLE, Msg.VISIBILITY_ARCHIVED),
            )
            .select_related("contact")
            .order_by("-id")
        )

        num_indexed = 0
        num_errored = 0
        before_id = start_msg.id
        last_uuid = None

        while True:
            batch = list(queryset.filter(id__lt=before_id)[:BATCH_SIZE])
            if not batch:
                break

            actions = [
                {
                    "_op_type": "create",
                    "_index": MESSAGES_INDEX_NAME,
                    "_source": {
                        "@timestamp": msg.created_on.isoformat(),
                        "org_id": msg.org_id,
                        "uuid": str(msg.uuid),
                        "contact_uuid": str(msg.contact.uuid),
                        "text": msg.text,
                    },
                }
                for msg in batch
            ]

            try:
                success, errors = helpers.bulk(os_client, actions, raise_on_error=False)
                num_indexed += success
                num_errored += len(errors)
                for error in errors:
                    self.stderr.write(f"  Error indexing: {error}")
            except Exception as e:
                self.stderr.write(f"Last UUID: {last_uuid}")
                raise CommandError(f"Bulk indexing failed: {e}")

            before_id = batch[-1].id
            last_uuid = batch[-1].uuid

            self.stdout.write(
                f" > Indexed {num_indexed} messages "
                f"(last uuid={last_uuid}, created_on={batch[-1].created_on.isoformat()}, "
                f"{num_errored} errored)"
            )

        self.stdout.write(f"Done. Indexed {num_indexed} messages total ({num_errored} errored).")

    def _get_os_client(self) -> OpenSearch:
        if not settings.OS_SERIES_COLLECTION_ID:
            raise CommandError("OS_SERIES_COLLECTION_ID must be configured")

        client = boto3.client(
            "opensearchserverless",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        resp = client.batch_get_collection(ids=[settings.OS_SERIES_COLLECTION_ID])
        details = resp.get("collectionDetails", [])
        if not details:
            raise CommandError(f"Collection {settings.OS_SERIES_COLLECTION_ID} not found")

        endpoint = details[0]["collectionEndpoint"]
        host = urlparse(endpoint).hostname

        session = boto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        auth = AWSV4SignerAuth(session.get_credentials(), settings.AWS_REGION, service="aoss")

        return OpenSearch(
            hosts=[{"host": host, "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
        )
