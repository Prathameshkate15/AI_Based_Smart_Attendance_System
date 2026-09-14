"""API Endpoints for Smart Attendance Management System"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from ..database import get_db
from ..models.user import User, AttendanceLog
from ..services.cv_service import CvPipeline

# Initialize CV pipeline (singleton per app session)
cv_pipeline = CvPipeline(confidence_threshold=0.5, liveness_threshold=0.7)

router = APIRouter(tags=["v1"])


@router.get("/health", include_in_schema=False)
async def health():
    """Health check endpoint."""
    system_status = cv_pipeline.get_system_status()
    return {
        "status": "healthy",
        "service": "attendance-api",
        "known_users": system_status["known_users_count"],
        "pipeline_ready": system_status["pipeline_ready"],
    }


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register_user(
    name: str,
    employee_id: str,
    face_images: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Register a new employee.

    - **name**: Employee full name
    - **employee_id**: Unique employee identifier
    - **face_images**: 5-10 face images for embedding extraction
    """
    # Check if employee already exists
    from sqlalchemy import select
    result = db.execute(select(User).where(User.employee_id == employee_id))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee ID already registered",
        )

    # Process face images and extract embeddings
    user_id = None
    for i, face_image in enumerate(face_images):
        # Read the uploaded file
        contents = await face_image.read()
        import numpy as np
        import cv2

        # Convert to image array
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image {i+1} could not be decoded",
            )

        # Register face and extract embedding
        result = cv_pipeline.register_face(
            user_id=i if user_id is None else user_id,
            face_image=img,
            name=name,
            employee_id=employee_id,
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Face registration failed: {result['error']}",
            )

        # Assign user_id from the first successful registration
        if user_id is None:
            user_id = i  # Simple indexing

    # Create user in database
    from sqlalchemy import select
    new_user = User(name=name, employee_id=employee_id)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "user_id": new_user.id,
        "name": new_user.name,
        "employee_id": new_user.employee_id,
        "embedding_dimension": cv_pipeline.known_embeddings.get(user_id, {}).get(
            "embedding_dimension", 128
        ),
        "message": f"Employee {name} registered successfully",
    }


@router.post("/clock-in", response_model=dict)
async def clock_in(
    employee_id: str,
    face_image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Clock in for an employee.

    - **employee_id**: Employee identifier
    - **face_image**: Live face image from camera feed
    """
    # Read the face image
    contents = await face_image.read()
    import numpy as np
    import cv2

    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not decode face image",
        )

    # Perform liveness detection first
    # For single image, we'll do a basic check
    # In production, use a sequence of frames
    # Basic liveness: check if image looks like a real face vs photo
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Simple variance check - live faces have more texture variation
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    is_live = laplacian_var > 100  # Threshold for texture variation

    if not is_live:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Liveness detection failed - possible photo spoof",
        )

    # Verify face against registered embeddings
    user_id, confidence, user_info = cv_pipeline.verify_face(img)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Face not recognized - employee not registered or face not matched",
        )

    # Check if employee exists in DB
    from sqlalchemy import select
    result = db.execute(select(User).where(User.employee_id == employee_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found in database",
        )

    # Record attendance log
    from datetime import datetime, timezone
    new_log = AttendanceLog(
        user_id=user.id,
        clock_in=datetime.now(timezone.utc),
        confidence=confidence,
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)

    return {
        "log_id": new_log.id,
        "user_id": user.id,
        "employee_id": user.employee_id,
        "name": user.name,
        "clock_in": new_log.clock_in.isoformat() if new_log.clock_in else None,
        "confidence": round(confidence, 4),
        "message": f"Clock-in successful for {user.name}",
    }


@router.get("/logs", response_model=List[dict])
async def get_attendance_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Retrieve attendance logs with pagination."""
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
            "name": log.user.name if log.user else None,
            "clock_in": log.clock_in.isoformat() if log.clock_in else None,
            "clock_out": log.clock_out.isoformat() if log.clock_out else None,
            "confidence": log.confidence,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.get("/users", response_model=List[dict])
async def get_registered_users(db: Session = Depends(get_db)):
    """Retrieve all registered users."""
    from sqlalchemy import select
    result = db.execute(select(User))
    users = result.scalars().all()
    return [
        {
            "id": user.id,
            "name": user.name,
            "employee_id": user.employee_id,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
        for user in users
    ]


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Delete a user and their associated data."""
    from sqlalchemy import select, delete as sql_delete

    # Check user exists
    result = db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Delete associated attendance logs first
    db.execute(sql_delete(AttendanceLog).where(AttendanceLog.user_id == user_id))
    db.delete(user)
    db.commit()

    return None