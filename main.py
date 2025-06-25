from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
import polars as pl
import io
import json

from checks import perform_checks

app = FastAPI()

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
    df = pl.read_csv(io.BytesIO(content))
    polars_results, polars_overall = perform_checks(df, checks_dict)

    return JSONResponse(content={
        "filename": file.filename,
            "dq_results": polars_results,
            "overall_pass": polars_overall
    })