"""
MinIO helper — common operations during local development.

Usage:
    python scripts/minio_helper.py list                    # list all files in bucket
    python scripts/minio_helper.py upload path/to/file.pdf # upload a single file
    python scripts/minio_helper.py upload-dir ./my-docs/   # upload a whole directory
    python scripts/minio_helper.py delete docs/old.pdf     # delete a file
    python scripts/minio_helper.py url docs/file.pdf       # get a pre-signed download URL
    python scripts/minio_helper.py buckets                 # list all buckets
    python scripts/minio_helper.py console                 # print the web console URL
"""

import sys
import os
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

import boto3
from botocore.config import Config
from config.settings import (
    S3_BUCKET, AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION, S3_ENDPOINT_URL
)

SUPPORTED_EXT = {".pdf", ".md"}


def _client():
    kwargs = {
        "aws_access_key_id":     AWS_ACCESS_KEY,
        "aws_secret_access_key": AWS_SECRET_KEY,
        "region_name":           AWS_REGION,
    }
    if S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = S3_ENDPOINT_URL
        kwargs["config"] = Config(s3={"addressing_style": "path"})
    return boto3.client("s3", **kwargs)


def cmd_list():
    s3 = _client()
    print(f"Bucket: s3://{S3_BUCKET}  ({S3_ENDPOINT_URL or 'AWS S3'})\n")
    paginator = s3.get_paginator("list_objects_v2")
    total = 0
    for page in paginator.paginate(Bucket=S3_BUCKET):
        for obj in page.get("Contents", []):
            size_kb = obj["Size"] / 1024
            print(f"  {obj['Key']:<60}  {size_kb:>8.1f} KB  {obj['LastModified'].strftime('%Y-%m-%d %H:%M')}")
            total += 1
    print(f"\n{total} file(s) total.")


def cmd_upload(path: str):
    p = Path(path)
    if not p.exists():
        print(f"Error: {path} does not exist")
        sys.exit(1)
    if p.suffix.lower() not in SUPPORTED_EXT:
        print(f"Warning: {p.suffix} is not a supported extension ({SUPPORTED_EXT})")
    s3 = _client()
    key = p.name
    s3.upload_file(str(p), S3_BUCKET, key)
    print(f"Uploaded {p} → s3://{S3_BUCKET}/{key}")


def cmd_upload_dir(directory: str):
    d = Path(directory)
    if not d.is_dir():
        print(f"Error: {directory} is not a directory")
        sys.exit(1)
    files = [f for f in d.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXT]
    if not files:
        print(f"No .pdf or .md files found in {directory}")
        return
    s3 = _client()
    for f in sorted(files):
        s3.upload_file(str(f), S3_BUCKET, f.name)
        print(f"  Uploaded: {f.name}")
    print(f"\nDone. {len(files)} file(s) uploaded to s3://{S3_BUCKET}/")


def cmd_delete(key: str):
    s3 = _client()
    s3.delete_object(Bucket=S3_BUCKET, Key=key)
    print(f"Deleted s3://{S3_BUCKET}/{key}")


def cmd_url(key: str, expiry: int = 3600):
    s3 = _client()
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=expiry,
    )
    print(f"Pre-signed URL (valid {expiry}s):\n{url}")


def cmd_buckets():
    s3 = _client()
    buckets = s3.list_buckets().get("Buckets", [])
    for b in buckets:
        print(f"  {b['Name']:<40}  created {b['CreationDate'].strftime('%Y-%m-%d')}")


def cmd_console():
    if S3_ENDPOINT_URL:
        host = S3_ENDPOINT_URL.replace(":9000", ":9001")
        print(f"MinIO web console: {host}")
        print(f"  Username: {AWS_ACCESS_KEY}")
        print(f"  Password: {AWS_SECRET_KEY}")
    else:
        print("Using real AWS S3 — no local console. Visit https://s3.console.aws.amazon.com/")


COMMANDS = {
    "list":       (cmd_list,       0),
    "upload":     (cmd_upload,     1),
    "upload-dir": (cmd_upload_dir, 1),
    "delete":     (cmd_delete,     1),
    "url":        (cmd_url,        1),
    "buckets":    (cmd_buckets,    0),
    "console":    (cmd_console,    0),
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    cmd, nargs = COMMANDS[sys.argv[1]]
    args = sys.argv[2:]
    if len(args) < nargs:
        print(f"Error: '{sys.argv[1]}' requires {nargs} argument(s)")
        sys.exit(1)
    cmd(*args[:nargs])
