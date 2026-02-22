import json
import os

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _bucket_policy(bucket_name: str) -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicRead",
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket_name}/*"],
            }
        ],
    }


def _policy_needs_update(client, bucket_name: str, desired_policy: dict) -> bool:
    try:
        current = client.get_bucket_policy(Bucket=bucket_name)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"NoSuchBucketPolicy", "NoSuchBucket"}:
            return True
        if code in {"AccessDenied", "AllAccessDisabled"}:
            return False
        raise

    current_policy = json.loads(current.get("Policy", "{}"))
    return current_policy != desired_policy


class Command(BaseCommand):
    help = "Create the S3/MinIO bucket and apply an optional public-read policy."

    def handle(self, *args, **options):
        storage_backend = settings.STORAGES["default"]["BACKEND"]
        if "storages.backends.s3" not in storage_backend:
            self.stdout.write(self.style.WARNING("Skipping storage bootstrap: not using S3 backend."))
            return

        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        endpoint_url = settings.AWS_S3_ENDPOINT_URL
        region_name = settings.AWS_S3_REGION_NAME

        create_bucket = _env_bool("STORAGE_BOOTSTRAP_BUCKET", True)
        set_policy = _env_bool("STORAGE_BOOTSTRAP_POLICY", True)
        public_read = _env_bool("STORAGE_BUCKET_PUBLIC_READ", True)

        if not create_bucket and not set_policy:
            self.stdout.write(self.style.WARNING("Storage bootstrap disabled via env."))
            return

        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region_name,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=Config(s3={"addressing_style": "path"}),
        )

        if create_bucket:
            if _bucket_exists(client, bucket_name):
                self.stdout.write(f"Bucket '{bucket_name}' already exists.")
            else:
                self._create_bucket(client, bucket_name, region_name)
                self.stdout.write(self.style.SUCCESS(f"Created bucket '{bucket_name}'."))

        if set_policy and public_read:
            policy = _bucket_policy(bucket_name)
            try:
                needs_update = _policy_needs_update(client, bucket_name, policy)
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                if code in {"AccessDenied", "AllAccessDisabled"}:
                    self.stdout.write(
                        self.style.WARNING(
                            "Bucket policy check skipped: access denied for GetBucketPolicy."
                        )
                    )
                    return
                raise

            if not needs_update:
                self.stdout.write(self.style.SUCCESS("Bucket policy already up to date."))
                return

            try:
                client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                if code in {"AccessDenied", "AllAccessDisabled"}:
                    self.stdout.write(
                        self.style.WARNING(
                            "Bucket policy bootstrap skipped: access denied for PutBucketPolicy."
                        )
                    )
                    return
                raise
            self.stdout.write(self.style.SUCCESS("Applied public-read bucket policy."))
        elif set_policy:
            self.stdout.write(self.style.WARNING("Bucket policy bootstrap skipped: public read disabled."))

    def _create_bucket(self, client, bucket_name: str, region_name: str) -> None:
        if region_name and region_name != "us-east-1":
            client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region_name},
            )
        else:
            client.create_bucket(Bucket=bucket_name)


def _bucket_exists(client, bucket_name: str) -> bool:
    try:
        client.head_bucket(Bucket=bucket_name)
        return True
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchBucket"}:
            return False
        raise
