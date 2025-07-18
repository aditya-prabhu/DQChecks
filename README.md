# Data Quality Checks API

This project provides a FastAPI-based REST API for performing data quality checks on structured data files (CSV, Parquet) stored locally or in Azure Blob Storage. It is designed for easy integration into data pipelines, dashboards, and cloud workflows.

## Features

- Validate CSV and Parquet files for nulls, value ranges, allowed values, uniqueness, data types, string length, and regex patterns.
- Supports file uploads and direct validation of files in Azure Blob Storage.
- Caches validation results in Azure Blob Storage for faster repeated checks.
- Customizable validation rules via JSON input.
- Efficient data processing using Polars.
- Can be deployed as an Azure Function App for serverless, scalable operation.
- Integrates easily with Azure Data Factory and other cloud services.

## Endpoints

- `/dq_checks_csv_export`: Upload a file and get a CSV of row-level check results.
- `/dq_checks_table_preview`: Upload a file and get a JSON preview of check results.
- `/dq_checks_full`: Upload a file and get full column-level check results.
- `/dq_checks_chunked_upload`: Upload large files in chunks for validation.
- `/dq_checks_blob_storage`: Validate a file stored in Azure Blob Storage.
- `/dq_checks_blob_storage_with_connection`: Validate a blob using a custom connection string and container.

## Running Locally

1. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

2. Set up your `.env` file with Azure Blob Storage connection details:
    ```
    AZURE_CONNECTION_STRING=your_connection_string
    BLOB_CONTAINER=your_container_name
    ```

3. Start the API server with Uvicorn (development mode with auto-reload):
    ```bash
    uvicorn main:app --reload
    ```

## Usage

- Send HTTP POST requests to the endpoints with files and validation rules.
- See endpoint docstrings and examples for request formats.

...existing code...

## Example Checks JSON

Below is a sample `checks` JSON string for validating columns.  
You can customize rules for each column as needed.

```json
{
  "use_cache": true,
  "checks": {
    "name": {
      "nullCheck": "true",
      "dataType": "string",
      "uniqueCheck": "true",
      "minLength": 2,
      "maxLength": 50,
      "allowedValues": ["Alice", "Bob", "Charlie"]
    },
    "address": {
      "nullCheck": "true",
      "dataType": "string",
      "minLength": 5,
      "maxLength": 100
    },
    "email": {
      "nullCheck": "true",
      "dataType": "string",
      "regex": "^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$"
    },
    "phone_number": {
      "nullCheck": "true",
      "dataType": "string",
      "regex": "^\\d{10}$"
    },
    "company": {
      "nullCheck": "true",
      "dataType": "string"
    },
    "job": {
      "nullCheck": "true",
      "dataType": "string"
    },
    "date_of_birth": {
      "nullCheck": "true",
      "dataType": "date",
      "valueRange": "1900-01-01,2024-12-31"
    },
    "ssn": {
      "nullCheck": "true",
      "dataType": "string",
      "uniqueCheck": "true",
      "regex": "^\\d{3}-\\d{2}-\\d{4}$"
    },
    "credit_card_number": {
      "nullCheck": "true",
      "dataType": "string",
      "regex": "^\\d{16}$"
    },
    "iban": {
      "nullCheck": "true",
      "dataType": "string",
      "minLength": 15,
      "maxLength": 34
    }
  }
}
```

## Deployment

- Can be deployed as an Azure Function App for serverless operation.
- Suitable for integration with Azure Data Factory, Logic Apps, or any workflow that can call HTTP APIs.

## Future Scope

- Support for additional file types (Excel, JSON).
- Direct validation of tables in SQL Server, Snowflake, and other databases.
- Enhanced reporting and notification features.
