import hashlib
import json
import datetime
import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

AZURE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")
CACHE_CONTAINER = os.getenv("CACHE_CONTAINER", "dqcache")
CACHE_TIMEOUT_SECONDS = int(os.getenv("CACHE_TIMEOUT_SECONDS", "300"))

def cache_blob_name(blob_name, checks_dict):
    """
    Generate a unique cache blob name for a file and checks combination.
    """
    checks_hash = hashlib.md5(json.dumps(checks_dict, sort_keys=True).encode()).hexdigest()
    return f"{blob_name}_{checks_hash}.json"

def get_cache_client():
    """
    Get the container client for the cache container.
    """
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    return blob_service_client.get_container_client(CACHE_CONTAINER)

def is_cache_valid(blob_client):
    """
    Check if the cache blob is within the timeout window.
    If not, delete the cache blob.
    """
    props = blob_client.get_blob_properties()
    last_modified = props.last_modified
    now = datetime.datetime.utcnow().replace(tzinfo=last_modified.tzinfo)
    age = (now - last_modified).total_seconds()
    if age < CACHE_TIMEOUT_SECONDS:
        return True
    else:
        try:
            blob_client.delete_blob()
        except Exception:
            pass
        return False

def read_cache(blob_name, checks_dict):
    """
    Read cached results for a file/checks combination if valid.
    """
    cache_name = cache_blob_name(blob_name, checks_dict)
    cache_client = get_cache_client()
    blob_client = cache_client.get_blob_client(cache_name)
    try:
        if blob_client.exists() and is_cache_valid(blob_client):
            cache_bytes = blob_client.download_blob().readall()
            return json.loads(cache_bytes)
    except Exception:
        pass
    return None

def write_cache(blob_name, checks_dict, result):
    """
    Write results to cache for a file/checks combination.
    """
    cache_name = cache_blob_name(blob_name, checks_dict)
    cache_client = get_cache_client()
    blob_client = cache_client.get_blob_client(cache_name)
    blob_client.upload_blob(json.dumps(result), overwrite=True)