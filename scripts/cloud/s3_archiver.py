"""
MinIO S3 Archiver
Uploads processed JSON files and raw PDFs to MinIO bucket
for archival storage. S3-compatible API.

Usage:
    python s3_archiver.py data/processed/well_approvals.json
    python s3_archiver.py sources/new_well_license_approvals_coordinates.pdf
"""

import sys
import os
from datetime import datetime
from minio import Minio
from minio.error import S3Error

MINIO_CONFIG = {
    "endpoint": os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000"),
    "access_key": os.getenv("MINIO_ROOT_USER", "minioadmin"),
    "secret_key": os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
    "bucket": os.getenv("MINIO_BUCKET", "mb-petro-archive"),
    "secure": False,
}


def get_client():
    return Minio(
        MINIO_CONFIG["endpoint"],
        access_key=MINIO_CONFIG["access_key"],
        secret_key=MINIO_CONFIG["secret_key"],
        secure=MINIO_CONFIG["secure"],
    )


def ensure_bucket(client):
    bucket = MINIO_CONFIG["bucket"]
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        print(f"Bucket '{bucket}' created.")
    return bucket


def upload_file(file_path: str):
    if not os.path.exists(file_path):
        print(f"ERROR: File not found: {file_path}")
        return

    client = get_client()
    bucket = ensure_bucket(client)

    file_name = os.path.basename(file_path)
    # Add timestamp prefix for versioning
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    object_name = f"{timestamp}_{file_name}"

    try:
        client.fput_object(bucket, object_name, file_path)
        print(f"Uploaded: {file_path} -> s3://{bucket}/{object_name}")
    except S3Error as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Upload a file to MinIO S3")
    parser.add_argument("file_path", help="Path to file to upload")
    args = parser.parse_args()
    upload_file(args.file_path)