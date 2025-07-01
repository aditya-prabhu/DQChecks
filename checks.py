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

def allowed_values_check(df, col, allowed_values):
    """Return True if all non-null values in the column are in allowed_values."""
    try:
        allowed_set = set(allowed_values)
        non_null_values = df.select(pl.col(col).drop_nulls()).to_series().to_list()
        return all(val in allowed_set for val in non_null_values)
    except Exception:
        return False

def unique_check(df, col):
    """Return True if all values in the column are unique."""
    try:
        return df.select(pl.col(col).is_unique()).item()
    except Exception:
        return False

def data_type_check(df, col, expected_type):
    """Return True if all non-null values in the column match the expected data type."""
    try:
        s = df[col].drop_nulls()
        if expected_type.lower() == "int":
            return all(isinstance(x, int) for x in s)
        elif expected_type.lower() == "float":
            return all(isinstance(x, float) or isinstance(x, int) for x in s)
        elif expected_type.lower() == "string":
            return all(isinstance(x, str) for x in s)
        elif expected_type.lower() == "boolean":
            return all(x in [True, False, "Y", "N"] for x in s)
        elif expected_type.lower() == "date":
            try:
                pl.Series(s).str.strptime(pl.Date, strict=False)
                return True
            except Exception:
                return False
        else:
            return False
    except Exception:
        return False

def min_length_check(df, col, min_length):
    """Return True if all non-null string values in the column have at least min_length characters."""
    try:
        s = df[col].drop_nulls()
        return all(len(str(x)) >= min_length for x in s)
    except Exception:
        return False

def max_length_check(df, col, max_length):
    """Return True if all non-null string values in the column have at most max_length characters."""
    try:
        s = df[col].drop_nulls()
        return all(len(str(x)) <= max_length for x in s)
    except Exception:
        return False

def regex_check(df, col, pattern):
    """Return True if all non-null string values in the column match the regex pattern."""
    import re
    try:
        s = df[col].drop_nulls()
        regex = re.compile(pattern)
        return all(bool(regex.fullmatch(str(x))) for x in s)
    except Exception:
        return False

def perform_checks(df, checks_dict):
    results = {}
    overall_pass = True
    print(df.columns)
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
        # Allowed values check
        if "allowedValues" in col_checks and col_checks["allowedValues"]:
            col_result["allowedValues"] = allowed_values_check(df, col, col_checks["allowedValues"])
            overall_pass = overall_pass and col_result["allowedValues"]
        # Unique check
        if col_checks.get("uniqueCheck", False) or col_checks.get("uniqueCheck", "") == "true":
            col_result["uniqueCheck"] = unique_check(df, col)
            overall_pass = overall_pass and col_result["uniqueCheck"]
        # Data type check
        if "dataType" in col_checks and col_checks["dataType"]:
            col_result["dataType"] = data_type_check(df, col, col_checks["dataType"])
            overall_pass = overall_pass and col_result["dataType"]
        # Min length check
        if "minLength" in col_checks and col_checks["minLength"]:
            col_result["minLength"] = min_length_check(df, col, int(col_checks["minLength"]))
            overall_pass = overall_pass and col_result["minLength"]
        # Max length check
        if "maxLength" in col_checks and col_checks["maxLength"]:
            col_result["maxLength"] = max_length_check(df, col, int(col_checks["maxLength"]))
            overall_pass = overall_pass and col_result["maxLength"]
        # Regex check
        if "regex" in col_checks and col_checks["regex"]:
            col_result["regex"] = regex_check(df, col, col_checks["regex"])
            overall_pass = overall_pass and col_result["regex"]
        results[col] = col_result
    return results, overall_pass