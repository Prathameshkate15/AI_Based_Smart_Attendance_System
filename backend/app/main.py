"""Smart Attendance Management System - Main FastAPI Application"""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
import uvicorn

from .api.endpoints import router as api_router
from .database import get_db, engine
from .models.user import Base
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text

# Initialize database tables
Base.metadata.create_all(bind=engine)
if "face_embedding" not in {column["name"] for column in inspect(engine).get_columns("users")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN face_embedding TEXT"))

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
    allow_origins=["*"],
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