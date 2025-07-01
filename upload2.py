import requests
import os
import math
import json

file_path = "./data/faker_100mb.csv"
filename = os.path.basename(file_path)
file_size = os.path.getsize(file_path)

num_chunks = 10
chunk_size = math.ceil(file_size / num_chunks)
total_chunks = math.ceil(file_size / chunk_size)

checks_dict = {
   "checks": {
       "name": {"nullCheck": "true"},
       "address": {"nullCheck": "true"},
       "email": {"nullCheck": "true"},
       "phone_number": {"nullCheck": "true"},
       "company": {"nullCheck": "true"},
       "job": {"nullCheck": "true"},
       "date_of_birth": {"nullCheck": "true"},
       "ssn": {"nullCheck": "true"},
       "credit_card_number": {"nullCheck": "true"},
       "iban": {"nullCheck": "true"}
   }
}

with open(file_path, "rb") as f:
    for chunk_number in range(1, total_chunks + 1):
        chunk_data = f.read(chunk_size)
        if not chunk_data:
            break
        response = requests.post(
            "http://localhost:8000/dq_checks_chunk",
            files={"file": (filename, chunk_data)},
            data={
                "filename": filename,
                "chunk_number": chunk_number,
                "total_chunks": total_chunks,
                "checks": json.dumps(checks_dict)
            },
        )
        print(
            f"Chunk {chunk_number}/{total_chunks} upload:",
            response.status_code,
            response.json(),
        )