from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import polars as pl
import io
import json
import os

from azure.storage.blob import BlobServiceClient, BlobClient
from checks import perform_checks

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chunk_buffers = {}

AZURE_CONNECTION_STRING = ""
BLOB_CONTAINER = "blobcontainer"

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
    """
    Reads a DataFrame from bytes, auto-detecting CSV or Parquet by file extension.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".parquet":
        return pl.read_parquet(io.BytesIO(file_bytes))
    else:
        return pl.read_csv(io.BytesIO(file_bytes))

@app.post("/dq_checks")
async def dq_checks(
    file: UploadFile = File(...),
    checks: str = Form(...)
):
    if not checks:
        return JSONResponse(status_code=400, content={"error": "checks field is required and must be a JSON string"})
    try:
        checks_dict = json.loads(checks)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid JSON for checks: {str(e)}"})

    content = await file.read()
    df = read_dataframe(content, file.filename)
    results, overall_results = perform_checks(df, checks_dict)

    return JSONResponse(content={
        "filename": file.filename,
        "dq_results": results,
        "overall_pass": overall_results
    })

@app.post("/dq_checks_chunk")
async def dq_checks_chunk(
    file: UploadFile = File(...),
    checks: str = Form(...),
    filename: str = Form(...),
    chunk_number: int = Form(...),
    total_chunks: int = Form(...)
):
    if not checks:
        return JSONResponse(status_code=400, content={"error": "checks field is required and must be a JSON string"})
    try:
        checks_dict = json.loads(checks)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid JSON for checks: {str(e)}"})

    chunk = await file.read()
    if filename not in chunk_buffers:
        chunk_buffers[filename] = []
    chunk_buffers[filename].append((chunk_number, chunk))

    if chunk_number == total_chunks:
        chunks = [c for _, c in sorted(chunk_buffers[filename], key=lambda x: x[0])]
        content = b"".join(chunks)
        del chunk_buffers[filename]

        df = read_dataframe(content, filename)
        polars_results, polars_overall = perform_checks(df, checks_dict)

        return JSONResponse(content={
            "filename": filename,
            "dq_results": polars_results,
            "overall_pass": polars_overall
        })
    else:
        return JSONResponse(content={
            "filename": filename,
            "chunk_number": chunk_number,
            "status": "in-progress"
        })

@app.post("/dq_checks_blob")
async def dq_checks_blob(
    blob_name: str = Form(...),
    checks: str = Form(...),
):
    if not checks:
        return JSONResponse(status_code=400, content={"error": "checks field is required and must be a JSON string"})
    try:
        checks_dict = json.loads(checks)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid JSON for checks: {str(e)}"})

    try:
        print("reading file")
        file_bytes = download_blob_to_bytes(blob_name)
    except Exception as e:
        return JSONResponse(status_code=404, content={"error": f"Blob '{blob_name}' not found or failed to download: {str(e)}"})

    print("converting to df")
    df = read_dataframe(file_bytes, blob_name)
    print("running validations")
    results, overall_results = perform_checks(df, checks_dict)

    # Delete the blob after processing
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER, blob=blob_name)
        blob_client.delete_blob()
        print(f"Deleted blob: {blob_name}")
    except Exception as e:
        print(f"Warning: Failed to delete blob '{blob_name}': {str(e)}")

    return JSONResponse(content={
        "filename": blob_name,
        "dq_results": results,
        "overall_pass": overall_results
    })