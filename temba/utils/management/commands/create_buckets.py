import json

from django.conf import settings
from django.core.management import BaseCommand

from temba.utils import s3

# buckets that should be publicly readable
PUBLIC_BUCKETS = {"attachments"}

# all buckets to create
BUCKETS = ["default", "attachments", "sessions", "archives"]


class Command(BaseCommand):
    help = "Creates S3 buckets that don't already exist."

    def add_arguments(self, parser):
        parser.add_argument("--testing", action="store_true")

    def handle(self, testing: bool, *args, **kwargs):
        # during tests settings.TESTING is true so table prefix is "test" - but this command is run with
        # settings.TESTING == False, so when setting up buckets for testing we need to override the prefix
        if testing:
            settings.AWS_S3_ENDPOINT_URL = "http://localhost:9000"
            settings.BUCKET_PREFIX = "test"

        client = s3.client()

        for bucket in BUCKETS:
            name = f"{settings.BUCKET_PREFIX}-{bucket}"
            is_public = bucket in PUBLIC_BUCKETS

            # create bucket without ACL (ACLs don't work reliably on MinIO)
            try:
                client.create_bucket(Bucket=name)
                self.stdout.write(f"🪣 created bucket {name}")
            except (client.exceptions.BucketAlreadyExists, client.exceptions.BucketAlreadyOwnedByYou):
                self.stdout.write(f"Bucket {name} already exists")

            # for public buckets, set a bucket policy to allow public read access
            if is_public:
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": ["*"]},
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{name}/*"],
                        }
                    ],
                }

                try:
                    client.put_bucket_policy(Bucket=name, Policy=json.dumps(policy))
                    self.stdout.write(f"   ✓ set public read policy on {name}")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"   ⚠ failed to set policy on {name}: {e}"))
