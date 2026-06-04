from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np
import json

from app.qa_engine import run_qa_analysis

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.post("/analyze")
async def analyze(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    options: str = Form(...)
):

    opts = json.loads(options)

    img1 = cv2.imdecode(np.frombuffer(await file1.read(), np.uint8), cv2.IMREAD_GRAYSCALE)
    img2 = cv2.imdecode(np.frombuffer(await file2.read(), np.uint8), cv2.IMREAD_GRAYSCALE)

    result_img = run_qa_analysis(img1, img2, opts)

    _, buffer = cv2.imencode(".png", result_img)

    import base64
    return {
        "image": "data:image/png;base64," + base64.b64encode(buffer).decode()
    }