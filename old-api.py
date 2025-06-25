from fastapi import FastAPI, File, UploadFile, Form
import os
from typing import Optional

app = FastAPI()

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    return {"filename": file.filename}

@app.post("/upload_chunk")
async def upload_chunk(
    file: UploadFile = File(...),
    filename: str = Form(...),
    chunk_number: int = Form(...),
    total_chunks: int = Form(...),
):
    temp_file_path = os.path.join(UPLOAD_FOLDER, f"{filename}.part")
    with open(temp_file_path, "ab") as buffer:
        buffer.write(await file.read())
    if chunk_number == total_chunks:
        final_path = os.path.join(UPLOAD_FOLDER, filename)
        os.rename(temp_file_path, final_path)
        return {"filename": filename, "status": "completed"}
    return {"filename": filename, "chunk_number": chunk_number, "status": "in-progress"}

@app.post("/upload_sample_chunk")
async def upload_sample_chunk(
    file: UploadFile = File(...)
):
    name, ext = os.path.splitext(file.filename)
    sample_path = os.path.join(UPLOAD_FOLDER, f"sample-{name}{ext}")
    with open(sample_path, "wb") as buffer:
        buffer.write(await file.read())
        
    # Run DQ checks here

    dq_passed = True
    if dq_passed:
        return {"filename": file.filename, "dq_status": "passed"}
    else:
        return {"filename": file.filename, "dq_status": "failed"}