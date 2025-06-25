import pandas as pd
import sys
import os
import pyarrow.parquet as pq

def get_csv_path(parquet_path):
    # If the file starts with 'sample-', remove it for the CSV name
    base_name = os.path.basename(parquet_path)
    if base_name.startswith('sample-'):
        base_name = base_name[len('sample-'):]
    base, _ = os.path.splitext(base_name)
    return os.path.join(os.path.dirname(parquet_path), base + ".csv")

def parquet_to_csv(parquet_path, csv_path=None):
    df = pd.read_parquet(parquet_path)
    if not csv_path:
        csv_path = get_csv_path(parquet_path)
    df.to_csv(csv_path, index=False)
    print(f"Converted '{parquet_path}' to '{csv_path}'.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parquet_to_csv.py <parquet_file> [csv_file]")
        sys.exit(1)
    parquet_file = sys.argv[1]
    csv_file = sys.argv[2] if len(sys.argv) > 2 else None
    parquet_to_csv(parquet_file, csv_file)
    table = pq.read_table(parquet_file)
    print(table.schema)