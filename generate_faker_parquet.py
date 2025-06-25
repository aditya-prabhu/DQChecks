import pandas as pd
from faker import Faker
import numpy as np
import pyarrow

fake = Faker()
num_rows = 2_000_000  # Adjust as needed to reach ~100MB
data = {
    "name": [fake.name() for _ in range(num_rows)],
    "address": [fake.address().replace('\n', ', ') for _ in range(num_rows)],
    "email": [fake.email() for _ in range(num_rows)],
    "phone_number": [fake.phone_number() for _ in range(num_rows)],
    "company": [fake.company() for _ in range(num_rows)],
    "job": [fake.job() for _ in range(num_rows)],
    "date_of_birth": [fake.date_of_birth(minimum_age=18, maximum_age=90) for _ in range(num_rows)],
    "ssn": [fake.ssn() for _ in range(num_rows)],
    "credit_card_number": [fake.credit_card_number() for _ in range(num_rows)],
    "iban": [fake.iban() for _ in range(num_rows)],
}

df = pd.DataFrame(data)
df.to_parquet("faker_100mb.parquet", engine="pyarrow")
print("Parquet file 'faker_100mb.parquet' created.")
