import azure.functions as func
import json
from dq_utils import read_dataframe
from checks import perform_checks
from azure.storage.blob import BlobServiceClient

app = func.FunctionApp()

@app.function_name(name="dq_checks_blob_storage_with_connection")
@app.route(route="dq_checks_blob_storage_with_connection", methods=["POST"])
async def main(req: func.HttpRequest) -> func.HttpResponse:
    form = await req.form()
    blob_name = form.get("blob_name")
    checks = form.get("checks")
    connection_string = form.get("connection_string")
    blob_container = form.get("blob_container")

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
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=blob_container, blob=blob_name)
        file_bytes = blob_client.download_blob().readall()
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": f"Blob '{blob_name}' not found or failed to download: {str(e)}"}),
            status_code=404,
            mimetype="application/json"
        )

    df = read_dataframe(file_bytes, blob_name)
    results, overall_results = perform_checks(df, checks_dict)

    return func.HttpResponse(
        json.dumps({
            "filename": blob_name,
            "dq_results": results,
            "overall_pass": overall_results
        }),
        mimetype="application/json"
    )