import os
from urllib.parse import urlparse

import boto3
from dotenv import load_dotenv

load_dotenv()

_s3 = boto3.client(
    "s3",
    region_name=os.environ["AWS_REGION"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
)

_BUCKET = os.environ["AWS_S3_BUCKET"]


def fetch_document_bytes(document_link: str) -> bytes:
    """Download the raw bytes of a document given its s3:// URI."""
    parsed = urlparse(document_link)
    if parsed.scheme != "s3":
        raise ValueError(f"Unsupported document_link scheme: {document_link!r}")

    bucket = parsed.netloc
    key = parsed.path.lstrip("/")

    response = _s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def upload_attachment_bytes(work_id: str, filename: str, content_bytes: bytes) -> str:
    """Upload one email attachment, keyed by the work_id it will belong to.
    Call this before inserting the work_item/document rows -- the returned
    s3:// URI is what gets stored as document_link."""
    key = f"invoices/{work_id}/{filename}"
    _s3.put_object(Bucket=_BUCKET, Key=key, Body=content_bytes)
    return f"s3://{_BUCKET}/{key}"
