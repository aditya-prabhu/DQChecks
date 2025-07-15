import azure.functions as func
import json
from dq_utils import read_dataframe, download_blob_to_bytes
from checks import perform_checks
import os
from azure.storage.blob import BlobServiceClient

AZURE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")
BLOB_CONTAINER = os.getenv("BLOB_CONTAINER")

app = func.FunctionApp()

@app.function_name(name="dq_checks_blob_storage")
@app.route(route="dq_checks_blob_storage", methods=["POST"])
async def main(req: func.HttpRequest) -> func.HttpResponse:
    form = await req.form()
    blob_name = form.get("blob_name")
    checks = form.get("checks")
    if not checks:
        return func.HttpResponse(
            json.dumps({"error": "checks field is required and must be a JSON string"}),
            status_code=400,
            mimetype="application/json"
        )
    try:
        checks_dict = json.loads(checks)
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": f"Invalid JSON for checks: {str(e)}"}),
            status_code=400,
            mimetype="application/json"
        )

    try:
        file_bytes = download_blob_to_bytes(blob_name)
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": f"Blob '{blob_name}' not found or failed to download: {str(e)}"}),
            status_code=404,
            mimetype="application/json"
        )

    df = read_dataframe(file_bytes, blob_name)
    results, overall_results = perform_checks(df, checks_dict)

    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER, blob=blob_name)
        blob_client.delete_blob()
    except Exception as e:
        # Log but do not fail the function if delete fails
        print(f"Warning: Failed to delete blob '{blob_name}': {str(e)}")

    return func.HttpResponse(
        json.dumps({
            "filename": blob_name,
            "dq_results": results,
            "overall_pass": overall_results
        }),
        mimetype="application/json"
    )