# Smart Attendance Management System - Architecture

## Overview
The Smart Attendance Management System follows a **Data-Driven Microservices Architecture** with three primary tiers:

## 1. Client Tier (Frontend & Edge Capture)
- **Framework:** React.js with WebRTC
- **Function:** UI dashboards and live video streaming from edge devices (webcams/kiosks)
- **Tech Stack:** React, Vite, navigator.mediaDevices.getUserMedia
- **Communication:** WebSocket/HTTP REST API to backend

## 2. Inference & Application Tier (Python Backend)
- **Framework:** FastAPI (asynchronous API routing)
- **Function:** Computer vision pipeline, face recognition, liveness detection, attendance logging
- **Tech Stack:** FastAPI, Uvicorn, OpenCV, DeepFace/InsightFace, SQLAlchemy, Redis
- **Key Services:**
  - CV Service (face detection, liveness, embedding extraction)
  - API Endpoints (registration, clock-in/out, logs, users)
  - MLOps (model training, tracking via MLflow)

## 3. Data & Vector Storage Tier
- **Relational Database:** PostgreSQL (primary) / SQLite (development)
  - Tables: `users`, `attendance_logs`, `model_versions`
  - Stores: user profiles, attendance records, model metadata
- **Vector Database:** FAISS / Milvus (for face embeddings)
  - Stores: 512-dimensional face embeddings for similarity search
  - Index types: IndexFlatIP (exact), IndexIVFFlat (approximate scalable)
- **Model Registry:** MLflow
  - Tracks model versions, metrics, and artifacts
  - Supports retraining pipeline via Celery

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLIENT TIER (React.js)                       │
│  ┌─────────────────┐  WebRTC  ┌─────────────────────────────┐ │
│  │ Live Camera     │ ────────→ │  FastAPI Backend (API)        │ │
│  │ Feed Component  │           │  ┌─────────────────────────┐ │ │
│  └─────────────────┘           │  │ CV Pipeline Service     │ │ │
│                               │  │  ┌──────────────────┐ │ │ │
│                               │  │  │ Face Detection   │ │ │ │
│                               │  │  └──────────────────┘ │ │ │
│                               │  │  ┌──────────────────┐ │ │ │
│                               │  │  │ Liveness Check   │ │ │ │
│                               │  │  └──────────────────┘ │ │ │
│                               │  │  ┌──────────────────┐ │ │ │
│                               │  │  │ Face Recognition │ │ │ │
│                               │  │  └──────────────────┘ │ │ │
│                               │  │  ┌──────────────────┐ │ │ │
│                               │  │  │ Attendance Log   │ │ │ │
│                               │  │  └──────────────────┘ │ │ │
│                               │  └─────────────────────────┘ │ │
│                               │  ┌─────────────────────────┐ │ │
│                               │  │ MLOps Service         │ │ │
│                               │  │  Model Training     │ │ │
│                               │  │  Model Tracking     │ │ │
│                               │  │  Model Retraining   │ │ │
│                               │  └─────────────────────────┘ │ │
│                               └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

                    ▲                                  │
                    │                                  │
                    └──────────────────────────────────┘
                 Vector Database (FAISS/Milvus)
                 + Relational Database (PostgreSQL/SQLite)