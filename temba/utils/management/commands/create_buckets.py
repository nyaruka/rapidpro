from botocore.client import ClientError

from django.conf import settings
from django.core.management import BaseCommand

from temba.utils import s3

BUCKETS = {
    "default": "private",
    "attachments": "public-read",
    "archives": "private",
}


class Command(BaseCommand):
    help = "Creates S3 buckets that don't already exist."

    def add_arguments(self, parser):
        parser.add_argument("--testing", action="store_true")

    def handle(self, testing: bool, *args, **kwargs):
        # during tests settings.TESTING is true so table prefix is "test" - but this command is run with
        # settings.TESTING == False, so when setting up buckets for testing we need to override the prefix
        if testing:
            settings.AWS_S3_ENDPOINT_URL = "http://localstack:4566"
            settings.BUCKET_PREFIX = "test"

        client = s3.client()

        for key, acl in BUCKETS.items():
            name = f"{settings.BUCKET_PREFIX}-{key}"
            try:
                client.head_bucket(Bucket=name)
                self.stdout.write(f"Bucket {name} already exists")
            except ClientError:
                client.create_bucket(Bucket=name, ACL=acl)
                self.stdout.write(f"🪣 created bucket {name}")
