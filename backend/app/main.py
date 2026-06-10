from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np
import json
import fitz  # PyMuPDF
import base64

from app.qa_engine import run_qa_analysis
from app.qa_engine import run_qa_with_report
from app.cad_engine import process_cad_files

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


# -------------------------
# UNIVERSAL LOADER (PDF + IMAGE)
# -------------------------
def load_input(file_bytes, filename):

    # ---------------- PDF ----------------
    if filename.lower().endswith(".pdf"):

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page = doc.load_page(0)

        pix = page.get_pixmap(dpi=300)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return gray

    # ---------------- IMAGE ----------------
    img = cv2.imdecode(
        np.frombuffer(file_bytes, np.uint8),
        cv2.IMREAD_GRAYSCALE
    )
    return img


@app.post("/analyze")
async def analyze(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    options: str = Form(...)
):
    opts = json.loads(options)
    file1_bytes = await file1.read()
    file2_bytes = await file2.read()

    is_dxf1 = file1.filename.lower().endswith('.dxf')
    is_dxf2 = file2.filename.lower().endswith('.dxf')

    if is_dxf1 and is_dxf2:
        img_bytes, report = process_cad_files(file1_bytes, file2_bytes, opts)
    else:
        img1 = load_input(file1_bytes, file1.filename)
        img2 = load_input(file2_bytes, file2.filename)
        img_bytes, report = run_qa_with_report(img1, img2, opts)

    b64_img = base64.b64encode(img_bytes).decode()
    return {"image": f"data:image/png;base64,{b64_img}", "report": report}