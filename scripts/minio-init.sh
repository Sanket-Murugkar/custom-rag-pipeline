#!/bin/sh
# Runs once inside the minio/mc container on first `docker compose up`.
# Creates the RAG bucket and uploads any .pdf or .md files from /sample-docs.

# Bug 6 fix: do NOT use `set -e` — the `until` retry loop needs to survive
# failed mc calls without the whole script aborting.

ALIAS="local"
ENDPOINT="http://minio:9000"
BUCKET="${MINIO_BUCKET:-rag-docs}"

echo "[minio-init] Waiting for MinIO to be ready..."
until mc alias set "$ALIAS" "$ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1; do
  sleep 2
done

echo "[minio-init] Connected to MinIO at $ENDPOINT"

# Create bucket (idempotent — mc mb is a no-op if bucket already exists with --ignore-existing)
mc mb --ignore-existing "$ALIAS/$BUCKET"
echo "[minio-init] Bucket '$BUCKET' ready"

# Upload every .pdf and .md file in /sample-docs
UPLOAD_COUNT=0
for f in /sample-docs/*.pdf /sample-docs/*.md; do
  [ -f "$f" ] || continue
  fname=$(basename "$f")
  mc cp "$f" "$ALIAS/$BUCKET/$fname" && \
    echo "[minio-init] Uploaded: $fname" && \
    UPLOAD_COUNT=$((UPLOAD_COUNT + 1))
done

if [ "$UPLOAD_COUNT" -eq 0 ]; then
  echo "[minio-init] No .pdf or .md files found in /sample-docs — bucket is empty."
  echo "[minio-init] Drop files into ./sample-docs/ and run: docker compose up minio-init"
else
  echo "[minio-init] Done. $UPLOAD_COUNT file(s) uploaded to s3://$BUCKET/"
fi

echo ""
echo "[minio-init] Bucket contents:"
mc ls "$ALIAS/$BUCKET"
