import azure.functions as func
import json
from dq_utils import read_dataframe
from checks import perform_checks

chunk_buffers = {}

app = func.FunctionApp()

@app.function_name(name="dq_checks_chunked_upload")
@app.route(route="dq_checks_chunked_upload", methods=["POST"])
async def main(req: func.HttpRequest) -> func.HttpResponse:
    form = await req.form()
    file = form.get("file")
    checks = form.get("checks")
    filename = form.get("filename")
    chunk_number = int(form.get("chunk_number"))
    total_chunks = int(form.get("total_chunks"))

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

        return func.HttpResponse(
            json.dumps({
                "filename": filename,
                "dq_results": polars_results,
                "overall_pass": polars_overall
            }),
            mimetype="application/json"
        )
    else:
        return func.HttpResponse(
            json.dumps({
                "filename": filename,
                "chunk_number": chunk_number,
                "status": "in-progress"
            }),
            mimetype="application/json"
        )