import requests
import os
import math
import pyarrow.parquet as pq
import pandas as pd

file_path = "./data/faker_100mb.parquet"
filename = os.path.basename(file_path)
file_size = os.path.getsize(file_path)

sample_parquet_path = "./data/sample-" + filename

parquet_file = pq.ParquetFile(file_path)
first_batch = next(parquet_file.iter_batches())
batch_df = first_batch.to_pandas()
batch_df.to_parquet(sample_parquet_path, index=False)

with open(sample_parquet_path, "rb") as f:
    sample_chunk = f.read()
    response = requests.post(
        "http://localhost:8000/upload_sample_chunk",
        files={"file": (f"sample-{filename}", sample_chunk)},
        data={"filename": filename},
    )
print("Sample chunk upload:", response.status_code, response.json())
if response.json().get("dq_status") != "passed":
    print("DQ check failed. Aborting upload.")
    if os.path.exists(sample_parquet_path):
        os.remove(sample_parquet_path)
    exit(1)

if os.path.exists(sample_parquet_path):
    os.remove(sample_parquet_path)

num_chunks = 10
chunk_size = math.ceil(file_size / num_chunks)
total_chunks = math.ceil(file_size / chunk_size)
with open(file_path, "rb") as f:
    for chunk_number in range(1, total_chunks + 1):
        chunk_data = f.read(chunk_size)
        if not chunk_data:
            break
        response = requests.post(
            "http://localhost:8000/upload_chunk",
            files={"file": (filename, chunk_data)},
            data={
                "filename": filename,
                "chunk_number": chunk_number,
                "total_chunks": total_chunks,
            },
        )
        print(
            f"Chunk {chunk_number}/{total_chunks} upload:",
            response.status_code,
            response.json(),
        )