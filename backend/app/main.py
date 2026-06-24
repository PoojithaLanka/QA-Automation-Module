from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np
import json
import fitz
import base64
import logging

from app.qa_engine import run_qa_with_report
from app.cad_engine import process_cad_files, render_dxf_preview
from app.mto_engine import extract_mto_from_dxf, extract_mto_from_image
from app.isometric_engine import generate_isometric, extract_segments_from_dxf, generate_segments_from_manual

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------
# CREATE FASTAPI APP
# -------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# -------------------------
# LOAD INPUT (image/PDF)
# -------------------------
def load_input(file_bytes, filename):
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
    else:
        img = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
        return img

# -------------------------
# QA ENDPOINT
# -------------------------
@app.post("/analyze")
async def analyze(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    options: str = Form(...)
):
    try:
        opts = json.loads(options)
        file1_bytes = await file1.read()
        file2_bytes = await file2.read()

        is_dxf1 = file1.filename.lower().endswith('.dxf')
        is_dxf2 = file2.filename.lower().endswith('.dxf')

        if is_dxf1 and is_dxf2:
            logger.info(f"Processing CAD files: {file1.filename} vs {file2.filename}")
            img_bytes, report = process_cad_files(file1_bytes, file2_bytes, opts)
        else:
            logger.info(f"Processing image/PDF files: {file1.filename} vs {file2.filename}")
            img1 = load_input(file1_bytes, file1.filename)
            img2 = load_input(file2_bytes, file2.filename)
            img_bytes, report = run_qa_with_report(img1, img2, opts)

        b64_img = base64.b64encode(img_bytes).decode()
        return {"image": f"data:image/png;base64,{b64_img}", "report": report}
    except Exception as e:
        logger.error(f"Error in analyze: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

# -------------------------
# DXF PREVIEW ENDPOINT
# -------------------------
@app.post("/preview")
async def dxf_preview(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.dxf'):
        raise HTTPException(400, "Only DXF files are supported")
    contents = await file.read()
    img_bytes = render_dxf_preview(contents)
    return Response(content=img_bytes, media_type="image/png")

# -------------------------
# MTO ENDPOINT
# -------------------------
@app.post("/mto")
async def material_take_off(file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1].lower()
    contents = await file.read()
    try:
        if ext == 'dxf':
            mto = extract_mto_from_dxf(contents)
        elif ext in ['png', 'jpg', 'jpeg', 'pdf']:
            if ext == 'pdf':
                doc = fitz.open(stream=contents, filetype="pdf")
                page = doc.load_page(0)
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
            else:
                img_bytes = contents
            mto = extract_mto_from_image(img_bytes)
        else:
            raise HTTPException(400, "Unsupported file type")
        return {"status": "success", "mto": mto}
    except Exception as e:
        logger.error(f"MTO error: {str(e)}", exc_info=True)
        raise HTTPException(500, f"MTO extraction failed: {str(e)}")

# -------------------------
# ISOMETRIC GENERATOR ENDPOINT
# -------------------------
# -------------------------
# ISOMETRIC GENERATOR ENDPOINT
# -------------------------
@app.post("/isometric/generate")
async def isometric_generate(
    file: UploadFile = File(None),
    segments: str = Form(None),
    rotation: float = Form(0),
    format: str = Form("png")
):
    try:
        if file and file.filename:
            contents = await file.read()
            if format == "json":
                segs = extract_segments_from_dxf(contents)
                return {"segments": segs, "fittings": [], "rotation": rotation}
            else:
                png_bytes = generate_isometric(file_bytes=contents, rotation_deg=rotation)
                return Response(content=png_bytes, media_type="image/png")
        elif segments:
            seg_list = json.loads(segments)
            if format == "json":
                data = generate_segments_from_manual(seg_list)  # returns dict with "segments" and "fittings"
                return {"segments": data["segments"], "fittings": data["fittings"], "rotation": rotation}
            else:
                png_bytes = generate_isometric(segments=seg_list, rotation_deg=rotation)
                return Response(content=png_bytes, media_type="image/png")
        else:
            raise HTTPException(400, "Either file or segments required")
    except Exception as e:
        logger.error(f"Isometric generation error: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Generation failed: {str(e)}")
# -------------------------
# HEALTH CHECK
# -------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}