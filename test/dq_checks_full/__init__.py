import azure.functions as func
import json
from dq_utils import read_dataframe
from checks import perform_checks  # Make sure this import works

app = func.FunctionApp()

@app.function_name(name="dq_checks_full")
@app.route(route="dq_checks_full", methods=["POST"])
async def main(req: func.HttpRequest) -> func.HttpResponse:
    form = await req.form()
    file = form.get("file")
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

    content = await file.read()
    df = read_dataframe(content, file.filename)
    results, overall_results = perform_checks(df, checks_dict)

    return func.HttpResponse(
        json.dumps({
            "filename": file.filename,
            "dq_results": results,
            "overall_pass": overall_results
        }),
        mimetype="application/json"
    )