from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import polars as pl
from dotenv import load_dotenv
import io
import json
import os
import csv

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

load_dotenv()

chunk_buffers = {}

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
    """
    Reads a DataFrame from bytes, auto-detecting CSV or Parquet by file extension.
    """
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

@app.post("/dq_checks_csv_export")
async def dq_checks_csv(
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
    df = df.head(50)  # Only first 50 rows, to match the table

    # Only use columns and checks specified in the uploaded JSON
    checks_dict_checks = checks_dict.get("checks", {})
    col_checks = []
    for col in checks_dict_checks:
        for check_name in checks_dict_checks[col]:
            col_checks.append({"col": col, "check": check_name})

    # Prepare table data: each row is a dict of (col, check) -> True/False
    rows = []
    for row_idx in range(len(df)):
        row_result = {}
        for pair in col_checks:
            col = pair["col"]
            check_name = pair["check"]
            check_val = checks_dict_checks[col][check_name]
            value = df[col][row_idx]
            passed = True
            try:
                if check_name == "nullCheck":
                    passed = value is not None
                elif check_name == "valueRange":
                    min_val, max_val = map(float, check_val.split(","))
                    passed = value is not None and min_val <= value <= max_val
                elif check_name == "allowedValues":
                    passed = value in check_val
                elif check_name == "uniqueCheck":
                    passed = df[col].to_list().count(value) == 1
                elif check_name == "dataType":
                    if check_val == "int":
                        passed = isinstance(value, int)
                    elif check_val == "float":
                        passed = isinstance(value, float) or isinstance(value, int)
                    elif check_val == "string":
                        passed = isinstance(value, str)
                    elif check_val == "boolean":
                        passed = value in [True, False, "Y", "N"]
                    elif check_val == "date":
                        try:
                            pl.Series([value]).str.strptime(pl.Date, strict=False)
                            passed = True
                        except Exception:
                            passed = False
                    else:
                        passed = False
                elif check_name == "minLength":
                    passed = value is not None and len(str(value)) >= int(check_val)
                elif check_name == "maxLength":
                    passed = value is not None and len(str(value)) <= int(check_val)
                elif check_name == "regex":
                    import re
                    passed = value is not None and re.fullmatch(check_val, str(value)) is not None
            except Exception:
                passed = False
            row_result[f"{col}|||{check_name}"] = passed
        rows.append(row_result)

    # Build CSV: header is [Row, col1-check1, col2-check2, ...]
    output = io.StringIO()
    writer = csv.writer(output)
    header = ["Row"] + [f"{cc['col']} - {cc['check']}" for cc in col_checks]
    writer.writerow(header)
    for idx, row in enumerate(rows):
        row_cells = [str(idx + 1)]
        for cc in col_checks:
            key = f"{cc['col']}|||{cc['check']}"
            val = row.get(key)
            if val is True:
                row_cells.append("PASS")
            elif val is False:
                row_cells.append("FAIL")
            else:
                row_cells.append("")
        writer.writerow(row_cells)
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=failed_checks.csv"})

@app.post("/dq_checks_table_preview")
async def dq_checks_table(
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
    df = df.head(50)  # Only first 50 rows

    # Only use columns and checks specified in the uploaded JSON
    checks_dict_checks = checks_dict.get("checks", {})
    # Build col_checks: list of (col, check) pairs actually specified
    col_checks = []
    for col in checks_dict_checks:
        for check_name in checks_dict_checks[col]:
            col_checks.append({"col": col, "check": check_name})

    # Prepare table data: each row is a dict of (col, check) -> True/False
    rows = []
    for row_idx in range(len(df)):
        row_result = {}
        for pair in col_checks:
            col = pair["col"]
            check_name = pair["check"]
            check_val = checks_dict_checks[col][check_name]
            value = df[col][row_idx]
            passed = True
            try:
                if check_name == "nullCheck":
                    passed = value is not None
                elif check_name == "valueRange":
                    min_val, max_val = map(float, check_val.split(","))
                    passed = value is not None and min_val <= value <= max_val
                elif check_name == "allowedValues":
                    passed = value in check_val
                elif check_name == "uniqueCheck":
                    passed = df[col].to_list().count(value) == 1
                elif check_name == "dataType":
                    if check_val == "int":
                        passed = isinstance(value, int)
                    elif check_val == "float":
                        passed = isinstance(value, float) or isinstance(value, int)
                    elif check_val == "string":
                        passed = isinstance(value, str)
                    elif check_val == "boolean":
                        passed = value in [True, False, "Y", "N"]
                    elif check_val == "date":
                        try:
                            pl.Series([value]).str.strptime(pl.Date, strict=False)
                            passed = True
                        except Exception:
                            passed = False
                    else:
                        passed = False
                elif check_name == "minLength":
                    passed = value is not None and len(str(value)) >= int(check_val)
                elif check_name == "maxLength":
                    passed = value is not None and len(str(value)) <= int(check_val)
                elif check_name == "regex":
                    import re
                    passed = value is not None and re.fullmatch(check_val, str(value)) is not None
            except Exception:
                passed = False
            row_result[f"{col}|||{check_name}"] = passed
        rows.append(row_result)

    # Remove blank columns in the result (i.e., only keep columns/checks that are performed)
    result = {
        "col_checks": col_checks,  # List of {col, check}
        "rows": rows
    }

    # Compute summary: for each column, how many rows failed at least one check
    col_fail_counts = {}
    col_fail_details = {}
    for pair in col_checks:
        col = pair["col"]
        check = pair["check"]
        if col not in col_fail_counts:
            col_fail_counts[col] = 0
        if col not in col_fail_details:
            col_fail_details[col] = {}
        if check not in col_fail_details[col]:
            col_fail_details[col][check] = 0
    for row in rows:
        # For each column, if any check for that column is False in this row, count as a fail
        col_failed = {col: False for col in col_fail_counts}
        for pair in col_checks:
            col, check = pair["col"], pair["check"]
            key = f"{col}|||{check}"
            if row.get(key) is False:
                col_failed[col] = True
                col_fail_details[col][check] += 1
        for col in col_failed:
            if col_failed[col]:
                col_fail_counts[col] += 1
    result["col_fail_counts"] = col_fail_counts
    result["col_fail_details"] = col_fail_details

    # Print results in table format to server console
    print("\nData Quality Check Results (first 50 rows, only user-specified columns/checks):")
    header = ["Row"] + [f"{cc['col']}-{cc['check']}" for cc in col_checks]
    print("\t".join(header))
    for idx, row in enumerate(result["rows"]):
        row_cells = [str(idx + 1)]
        for cc in col_checks:
            col, check = cc["col"], cc["check"]
            val = row.get(f"{col}|||{check}", "")
            if val is True:
                row_cells.append("✔️")
            elif val is False:
                row_cells.append("❌")
            else:
                row_cells.append("")
        print("\t".join(row_cells))
    print("\nColumn fail summary (number of rows with at least one failed check):")
    print(json.dumps(col_fail_counts, indent=2))
    print("\nColumn fail details (number of fails per check):")
    print(json.dumps(col_fail_details, indent=2))

    return JSONResponse(content=result)

@app.post("/dq_checks_full")
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

@app.post("/dq_checks_chunked_upload")
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

@app.post("/dq_checks_blob_storage")
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

@app.post("/dq_checks_blob_storage_with_connection")
async def dq_checks_blob_with_connection(
    blob_name: str = Form(...),
    checks: str = Form(...),
    connection_string: str = Form(...),
    blob_container: str = Form(None)
):
    if not checks:
        return JSONResponse(status_code=400, content={"error": "checks field is required and must be a JSON string"})
    try:
        checks_dict = json.loads(checks)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid JSON for checks: {str(e)}"})

    try:
        container = blob_container if blob_container else BLOB_CONTAINER
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=container, blob=blob_name)
        file_bytes = blob_client.download_blob().readall()
    except Exception as e:
        return JSONResponse(status_code=404, content={"error": f"Blob '{blob_name}' not found or failed to download: {str(e)}"})

    df = read_dataframe(file_bytes, blob_name)
    results, overall_results = perform_checks(df, checks_dict)

    return JSONResponse(content={
        "filename": blob_name,
        "dq_results": results,
        "overall_pass": overall_results
    })