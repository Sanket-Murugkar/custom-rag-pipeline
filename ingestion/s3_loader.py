"""
S3 loader — lists PDF and .md files in the bucket,
downloads each, and returns raw text + metadata.
Tracks ingested files in a local state file to skip unchanged docs.

Works with both:
  • Real AWS S3  — set standard AWS_* env vars; leave S3_ENDPOINT_URL empty.
  • MinIO (local) — set S3_ENDPOINT_URL=http://localhost:9000 plus
                    AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY matching
                    MINIO_ROOT_USER / MINIO_ROOT_PASSWORD.
"""

import io
import json
from pathlib import Path
from typing import Generator

import boto3
from botocore.config import Config
import pypdf
import markdown_it

from config.settings import (
    S3_BUCKET, AWS_REGION, AWS_ACCESS_KEY, AWS_SECRET_KEY, S3_ENDPOINT_URL
)

STATE_FILE    = Path(".ingestion_state.json")
SUPPORTED_EXT = {".pdf", ".md"}


def _s3_client():
    """
    Returns a boto3 S3 client configured for either AWS S3 or MinIO.
    When S3_ENDPOINT_URL is set (MinIO / any S3-compatible store):
      - endpoint_url overrides the AWS endpoint
      - path-style addressing is forced (MinIO requires it;
        virtual-hosted-style breaks with localhost)
    """
    kwargs = {
        "region_name":           AWS_REGION,
        "aws_access_key_id":     AWS_ACCESS_KEY,
        "aws_secret_access_key": AWS_SECRET_KEY,
    }
    if S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = S3_ENDPOINT_URL
        kwargs["config"] = Config(s3={"addressing_style": "path"})

    return boto3.client("s3", **kwargs)


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _etag(obj_summary) -> str:
    # ETags from S3/MinIO are wrapped in double-quotes
    return obj_summary["ETag"].strip('"')


def _extract_pdf(data: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(data))
    pages  = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _extract_md(data: bytes) -> str:
    # Bug 8 fix: return the raw markdown text rather than trying to
    # reconstruct it from tokens. markdown-it-py's token tree is lossy
    # for tables and fenced code blocks. Embedding models handle markdown
    # syntax fine — the raw text is actually better context.
    return data.decode("utf-8", errors="replace")


def load_documents(force: bool = False) -> Generator[dict, None, None]:
    """
    Yields dicts: {key, text, source, etag}
    Skips files whose ETag hasn't changed since last run (unless force=True).
    State is only written after all documents are yielded so a mid-run
    crash doesn't mark failed files as successfully ingested.
    """
    s3      = _s3_client()
    state   = _load_state()
    updated = dict(state)

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET):
        for obj in page.get("Contents", []):
            key  = obj["Key"]
            ext  = Path(key).suffix.lower()
            etag = _etag(obj)

            if ext not in SUPPORTED_EXT:
                continue

            if not force and state.get(key) == etag:
                print(f"  [skip] {key} — unchanged")
                continue

            print(f"  [load] {key}")
            try:
                response = s3.get_object(Bucket=S3_BUCKET, Key=key)
                data     = response["Body"].read()
            except Exception as e:
                print(f"  [warn] could not fetch {key}: {e}")
                continue

            try:
                text = _extract_pdf(data) if ext == ".pdf" else _extract_md(data)
            except Exception as e:
                print(f"  [warn] could not parse {key}: {e}")
                continue

            if not text.strip():
                print(f"  [warn] {key} yielded no text — skipping")
                continue

            # Only record the etag once we have successfully extracted text
            updated[key] = etag
            yield {"key": key, "text": text, "source": key, "etag": etag}

    _save_state(updated)
