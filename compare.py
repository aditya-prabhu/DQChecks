from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from typing import List
import pandas as pd
import polars as pl
import dask.dataframe as dd
import io
import json
import time
import tempfile
import os

app = FastAPI()

def dq_null_check_pandas(df, checks_dict):
    results = {}
    overall_pass = True
    for col, col_checks in checks_dict.get("checks", {}).items():
        col_result = {}
        if col_checks.get("nullCheck", False) or col_checks.get("nullCheck", "") == "true":
            col_result["nullCheck"] = bool(df[col].isnull().sum() == 0)
            overall_pass = overall_pass and col_result["nullCheck"]
        results[col] = col_result
    return results, overall_pass

def dq_null_check_polars(df, checks_dict):
    results = {}
    overall_pass = True
    for col, col_checks in checks_dict.get("checks", {}).items():
        col_result = {}
        if col_checks.get("nullCheck", False) or col_checks.get("nullCheck", "") == "true":
            col_result["nullCheck"] = bool(df.select(pl.col(col).is_null().sum()).item() == 0)
            overall_pass = overall_pass and col_result["nullCheck"]
        results[col] = col_result
    return results, overall_pass

def dq_null_check_dask(df, checks_dict):
    results = {}
    overall_pass = True
    for col, col_checks in checks_dict.get("checks", {}).items():
        col_result = {}
        if col_checks.get("nullCheck", False) or col_checks.get("nullCheck", "") == "true":
            nulls = df[col].isnull().sum().compute()
            col_result["nullCheck"] = bool(nulls == 0)
            overall_pass = overall_pass and col_result["nullCheck"]
        results[col] = col_result
    return results, overall_pass

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

    # Pandas
    t0 = time.time()
    df_pandas = pd.read_csv(io.BytesIO(content))
    pandas_results, pandas_overall = dq_null_check_pandas(df_pandas, checks_dict)
    pandas_time = time.time() - t0

    # Polars
    t1 = time.time()
    df_polars = pl.read_csv(io.BytesIO(content))
    polars_results, polars_overall = dq_null_check_polars(df_polars, checks_dict)
    polars_time = time.time() - t1

    # Dask (requires a file path)
    t2 = time.time()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    df_dask = dd.read_csv(tmp_path)
    dask_results, dask_overall = dq_null_check_dask(df_dask, checks_dict)
    dask_time = time.time() - t2
    os.unlink(tmp_path)

    print(f"Pandas time: {pandas_time:.4f}s")
    print(f"Polars time: {polars_time:.4f}s")
    print(f"Dask time: {dask_time:.4f}s")

    return JSONResponse(content={
        "filename": file.filename,
        "pandas": {
            "dq_results": pandas_results,
            "overall_pass": pandas_overall,
            "time_seconds": pandas_time
        },
        "polars": {
            "dq_results": polars_results,
            "overall_pass": polars_overall,
            "time_seconds": polars_time
        },
        "dask": {
            "dq_results": dask_results,
            "overall_pass": dask_overall,
            "time_seconds": dask_time
        }
    })