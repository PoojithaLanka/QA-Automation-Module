# PRAXSOL QA DRAWING INSPECTOR

## Overview
AI-powered QA system for engineering drawings that detects:
- Structural changes
- Missing annotations
- Potential clashes

## Tech Stack
- FastAPI (Backend)
- OpenCV + SSIM (Image comparison)
- EasyOCR (Text detection)
- React + Vite (Frontend)

## How to Run

### Backend
uvicorn app.main:app --reload


### Frontend

npm install
npm run dev


## Features
- Upload 2 drawings
- Select analysis type
- Get annotated QA result image
- View issue report

## Output Colors
- Red: Changes
- Blue: Annotation
- Orange: Clashes