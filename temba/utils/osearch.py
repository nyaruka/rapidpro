from urllib.parse import urlparse

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

from django.conf import settings


def get_client() -> OpenSearch:
    parsed = urlparse(settings.OPENSEARCH_ENDPOINT_URL)
    use_ssl = parsed.scheme == "https"

    kwargs = {}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:  # pragma: no cover
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
