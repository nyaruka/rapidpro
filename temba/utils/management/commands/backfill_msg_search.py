from urllib.parse import urlparse

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection, helpers

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db.models import Q
from django.db.models.functions import Length

from temba.msgs.models import Msg

MESSAGES_INDEX_BASE = "messages-v1"
BATCH_SIZE = 500


class Command(BaseCommand):
    help = "Backfills messages from the database into the OpenSearch messages index."

    def add_arguments(self, parser):
        parser.add_argument(
            "--start-uuid", help="UUID of the message to start from (works backwards from here)", default=None
        )

    def handle(self, start_uuid: str | None, *args, **options):
        if not settings.OPENSEARCH_ENDPOINT_URL:
            raise CommandError("OPENSEARCH_ENDPOINT_URL must be configured")

        os_client = self._get_client()

        queryset = (
            Msg.objects.annotate(text_len=Length("text"))
            .filter(
                Q(direction=Msg.DIRECTION_IN) | Q(broadcast__isnull=True, created_by__isnull=False),
                text_len__gte=2,
                visibility__in=(Msg.VISIBILITY_VISIBLE, Msg.VISIBILITY_ARCHIVED),
            )
            .exclude(msg_type=Msg.TYPE_VOICE)
            .select_related("contact")
            .order_by("-uuid")
        )

        num_indexed = 0
        num_errored = 0
        last_uuid = None

        while True:
            qs = queryset.filter(uuid__lt=start_uuid) if start_uuid else queryset
            batch = list(qs[:BATCH_SIZE])
            if not batch:
                break

            actions = [
                {
                    "_op_type": "index",
                    "_index": f"{MESSAGES_INDEX_BASE}-{msg.created_on.strftime('%Y-%m')}",
                    "_id": str(msg.uuid),
                    "_routing": str(msg.org_id),
                    "_source": {
                        "contact_uuid": str(msg.contact.uuid),
                        "text": msg.text,
                        "in_ticket": msg.ticket_uuid is not None,
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

            last_uuid = str(batch[-1].uuid)
            start_uuid = last_uuid

            self.stdout.write(
                f" > Indexed {num_indexed} messages "
                f"(last uuid={last_uuid}, created_on={batch[-1].created_on.isoformat()}, "
                f"{num_errored} errored)"
            )

        self.stdout.write(f"Done. Indexed {num_indexed} messages total ({num_errored} errored).")

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
