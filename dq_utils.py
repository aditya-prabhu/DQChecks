import os
import io
import polars as pl
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient, BlobClient

load_dotenv()

AZURE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")
BLOB_CONTAINER = os.getenv("BLOB_CONTAINER")

def download_blob_to_bytes(blob_name: str):
    MAX_SINGLE_GET_SIZE = 12 * 1024 * 1024
    MAX_CHUNK_GET_SIZE = 2 * 1024 * 1024
    MAX_CONCURRENCY = 8

    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    blob_client = BlobClient(
        account_url=blob_service_client.url,
        container_name=BLOB_CONTAINER,
        blob_name=blob_name,
        credential=blob_service_client.credential,
        max_single_get_size=MAX_SINGLE_GET_SIZE,
        max_chunk_get_size=MAX_CHUNK_GET_SIZE
    )
    stream = blob_client.download_blob(max_concurrency=MAX_CONCURRENCY)
    return stream.readall()

def read_dataframe(file_bytes: bytes, filename: str):
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".parquet":
        return pl.read_parquet(io.BytesIO(file_bytes))
    else:
        return pl.read_csv(io.BytesIO(file_bytes))

def get_failed_summary(results):
    """
    Returns a summary dict of all failed checks per column.
    Example: { "col1": ["null_check", "unique_check"], ... }
    """
    failed_summary = {}
    for col, checks in results.items():
        failed_checks = [check_name for check_name, status in checks.items() if status is False]
        if failed_checks:
            failed_summary[col] = failed_checks
    return failed_summary
