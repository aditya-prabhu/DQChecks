import azure.functions as func
import json
from dq_utils import read_dataframe

app = func.FunctionApp()

@app.function_name(name="dq_checks_table_preview")
@app.route(route="dq_checks_table_preview", methods=["POST"])
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
    df = df.head(50)  # Only first 50 rows

    checks_dict_checks = checks_dict.get("checks", {})
    col_checks = []
    for col in checks_dict_checks:
        for check_name in checks_dict_checks[col]:
            col_checks.append({"col": col, "check": check_name})

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
                        import polars as pl
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

    result = {
        "col_checks": col_checks,
        "rows": rows,
        "col_fail_counts": col_fail_counts,
        "col_fail_details": col_fail_details
    }

    return func.HttpResponse(
        json.dumps(result),
        mimetype="application/json"
    )