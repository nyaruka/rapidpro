from urllib.parse import urlparse

import boto3
from elasticsearch import Elasticsearch
from requests_aws4auth import AWS4Auth

from django.conf import settings


def get_client() -> Elasticsearch:
    parsed = urlparse(settings.ELASTICSEARCH_ENDPOINT_URL)
    use_ssl = parsed.scheme == "https"

    kwargs = {}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:  # pragma: no cover
        session = boto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        credentials = session.get_credentials()
        kwargs["http_auth"] = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            settings.AWS_REGION,
            "es",
            session_token=credentials.token,
        )

    host = parsed.hostname
    port = parsed.port or (443 if use_ssl else 9200)
    scheme = "https" if use_ssl else "http"

    return Elasticsearch(
        hosts=[f"{scheme}://{host}:{port}"],
        verify_certs=use_ssl,
        **kwargs,
    )
