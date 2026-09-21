"""Smart Attendance Management System - Main FastAPI Application"""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
import uvicorn
import os

from .api.endpoints import router as api_router
from .database import get_db, engine
from .models.user import Base
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text

# Initialize database tables
Base.metadata.create_all(bind=engine)
user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
if "face_embedding" not in user_columns:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN face_embedding TEXT"))
if "updated_at" not in user_columns:
    # Older demo databases predate the update timestamp on User.
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN updated_at TIMESTAMP"))
log_columns = {column["name"] for column in inspect(engine).get_columns("attendance_logs")}
for column, definition in (
    ("anomaly_status", "VARCHAR(20) NOT NULL DEFAULT 'NORMAL'"),
    ("anomaly_score", "FLOAT"),
    ("anomaly_reason", "TEXT"),
):
    if column not in log_columns:
        with engine.begin() as connection:
            connection.execute(text(f"ALTER TABLE attendance_logs ADD COLUMN {column} {definition}"))

app = FastAPI(
    title="Smart Attendance Management System API",
    description="AI-powered biometric attendance tracking system",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1", tags=["v1"])


@app.get("/", tags=["root"])
async def root():
    """Root endpoint."""
    return {
        "message": "Smart Attendance Management System API",
        "version": "0.1.0",
        "status": "operational",
    }


@app.get("/health", tags=["health"], include_in_schema=False)
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "attendance-api"}


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)