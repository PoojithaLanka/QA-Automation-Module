# QA DRAWING INSPECTOR
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136+-green.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-blue.svg)](https://reactjs.org)

**Automated quality assurance for engineering drawings – compare two drawings, highlight differences, and generate detailed reports.**

## Overview
The **QA Drawing Inspector** is a web‑based tool that automates the comparison of engineering drawings (isometrics, P&IDs, layouts). It supports:

- **Raster images** (PNG, JPG, JPEG) and **PDF files** (first page)
- **DXF CAD files** (native AutoCAD exchange format)

The tool detects **changes**, **clashes**, **missing annotations**, and **unlabeled components**. For DXF files it also identifies **moved**, **modified**, **missing**, **added** entities, and **clashes** with detailed tables (type, layer, change description, position).

Built as an internship project, it demonstrates a full‑stack implementation with a modern React frontend, a FastAPI backend, and advanced algorithms (feature matching, Hungarian assignment, offset voting, OCR).

## ✨ Features

### Core QA Pipelines

| Feature | Image / PDF | DXF |
|---------|-------------|-----|
| Automatic alignment (scale/rotation robust) | ✅ ORB + homography | ✅ Global + per‑layer offset voting |
| Change detection (new / removed components) | ✅ IoU | ✅ Hungarian matching |
| Modification detection (geometry changed) | ❌ (only presence/absence) | ✅ Shape‑key + type‑level matching |
| Clash detection (overlapping components) | ✅ Centroid distance (<10px) | ✅ Bounding box overlap (+5px margin) |
| Annotation / text comparison | ✅ EasyOCR (proximity) | ✅ Fuzzy text matching (case/punctuation‑insensitive) |
| Dimension value comparison | ❌ | ✅ Tolerance‑based |
| Block attributes (valves, fittings) | ❌ | ✅ Extracted and reported |
| Partial report (warnings) | ❌ | ✅ (skips malformed entities) |

### User Interface

- Drag‑and‑drop file upload
- Real‑time preview (images, PDFs, DXF rendered preview)
- Dynamic checkboxes – options change based on file type
- Result image with colour‑coded bounding boxes
- Interactive report: stat cards, bar chart, detailed tables (for DXF)
---
### Additional Utilities

- DXF preview endpoint (`/preview`) – renders a clean PNG of a single DXF
- Unit tests (`pytest`) for the CAD engine
- All thresholds configurable via `config.json`

---
## 🧰 Technology Stack

| Layer | Technologies |
|-------|--------------|
| **Frontend** | React 18, Vite, Axios, Chart.js |
| **Backend** | FastAPI (Python 3.10+), Uvicorn |
| **Image Processing** | OpenCV, PyMuPDF (fitz), EasyOCR |
| **CAD Processing** | ezdxf, scipy (Hungarian algorithm), matplotlib |
| **Testing** | pytest |

---
## 🚀 Installation & Setup

### Prerequisites

- **Python 3.10 or higher** (3.14 recommended)
- **Node.js 16+** and npm
- Git (optional)

### 1. Clone the repository

```bash
git clone https://github.com/your-username/qa-drawing-inspector.git
cd qa-drawing-inspector
```
## Backend setup
```bash
cd backend
python -m venv venv
source venv/bin/activate      # Linux/Mac
# or .\venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### Frontend setup
```bash
cd ../frontend
npm install
```
### Run the application
- Backend (from backend/ folder):
```bash
uvicorn app.main:app --reload
```
- Frontend (from frontend/ folder):
```bash
npm run dev
```
-Open your browser at http://localhost:3000.

### 🧪 Running Tests
- From the backend/ folder (with virtual environment activated):
```bash
pytest tests/test_cad_engine.py -v
```
This runs 15+ unit tests covering entity extraction, offset voting, Hungarian matching, and fingerprinting.

