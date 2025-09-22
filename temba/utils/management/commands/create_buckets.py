from botocore.exceptions import ClientError

from django.conf import settings
from django.core.management import BaseCommand

from temba.utils import s3


class Command(BaseCommand):
    help = "Creates S3 buckets that don't already exist."

    def handle(self, *args, **kwargs):
        self.client = s3.client()

        for key, bucket in settings.BUCKETS.items():
            try:
                self.client.create_bucket(Bucket=bucket)
            except ClientError as e:
                print(f"Error creating bucket: {e}")
