import polars as pl

def null_check(df, col):
    """Return True if no nulls in the column, else False."""
    return bool(df.select(pl.col(col).is_null().sum()).item() == 0)

def value_range_check(df, col, value_range):
    """Return True if all values in the column are within the given range (inclusive)."""
    try:
        min_val, max_val = map(float, value_range.split(","))
        in_range = df.select(((pl.col(col) >= min_val) & (pl.col(col) <= max_val)).all()).item()
        return bool(in_range)
    except Exception:
        return False

def perform_checks(df, checks_dict):
    results = {}
    overall_pass = True
    for col, col_checks in checks_dict.get("checks", {}).items():
        col_result = {}
        # Null check
        if col_checks.get("nullCheck", False) or col_checks.get("nullCheck", "") == "true":
            col_result["nullCheck"] = null_check(df, col)
            overall_pass = overall_pass and col_result["nullCheck"]
        # Value range check
        if "valueRange" in col_checks and col_checks["valueRange"]:
            col_result["valueRange"] = value_range_check(df, col, col_checks["valueRange"])
            overall_pass = overall_pass and col_result["valueRange"]
        results[col] = col_result
    return results, overall_pass