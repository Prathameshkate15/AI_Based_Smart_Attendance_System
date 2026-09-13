from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from db import get_db
from models import User, AttendanceLog

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/health", include_in_schema=False)
async def health():
    return {"status": "healthy", "service": "attendance-api"}


@router.post("/register", response_model=dict)
async def register_user(
    name: str,
    employee_id: str,
    db: Session = Depends(get_db),
):
    """Register a new employee with name and employee ID."""
    from sqlalchemy import select
    result = db.execute(select(User).where(User.employee_id == employee_id))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee ID already registered",
        )
    user = User(name=name, employee_id=employee_id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"user_id": user.id, "name": user.name, "employee_id": user.employee_id}


@router.post("/clock-in", response_model=dict)
async def clock_in(
    employee_id: str,
    confidence: float,
    db: Session = Depends(get_db),
):
    """Record a clock-in event for an employee."""
    from sqlalchemy import select
    result = db.execute(select(User).where(User.employee_id == employee_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found. Register first.",
        )
    log = AttendanceLog(user_id=user.id, clock_in=None, confidence=confidence)
    db.add(log)
    db.commit()
    db.refresh(log)
    return {
        "log_id": log.id,
        "user_id": user.id,
        "employee_id": user.employee_id,
        "clock_in": log.clock_in.isoformat() if log.clock_in else None,
        "confidence": confidence,
    }


@router.get("/logs", response_model=List[dict])
async def get_attendance_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Retrieve attendance logs."""
    from sqlalchemy import select, desc
    result = db.execute(
        select(AttendanceLog)
        .order_by(desc(AttendanceLog.created_at))
        .offset(skip)
        .limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "employee_id": log.user.employee_id if log.user else None,
            "clock_in": log.clock_in.isoformat() if log.clock_in else None,
            "confidence": log.confidence,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]