"""API Endpoints for Smart Attendance Management System"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import json
import numpy as np
import os
import csv
import io
import hmac

from ..database import get_db
from ..models.user import User, AttendanceLog
from ..services.cv_service import CvPipeline
from ..auth import issue_token, require_admin

# Initialize CV pipeline (singleton per app session)
cv_pipeline = CvPipeline(confidence_threshold=0.5, liveness_threshold=0.7)

router = APIRouter(tags=["v1"])


@router.post("/admin/login", response_model=dict)
async def admin_login(username: str = Form(...), password: str = Form(...)):
    """Start an admin session using credentials supplied through environment variables."""
    expected_username = os.getenv("ADMIN_USERNAME", "admin")
    expected_password = os.getenv("ADMIN_PASSWORD", "admin123")
    if not hmac.compare_digest(username, expected_username) or not hmac.compare_digest(password, expected_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")
    return {"token": issue_token(username), "username": username}


def load_database_embeddings(db: Session) -> None:
    """Load persisted face vectors so recognition survives API restarts."""
    # Rebuild the in-memory index so deleted employees cannot remain recognizable.
    cv_pipeline.known_embeddings.clear()
    cv_pipeline.known_users.clear()
    users = db.query(User.id, User.name, User.employee_id, User.face_embedding).filter(
        User.face_embedding.isnot(None)
    ).all()
    for user in users:
        try:
            embedding = np.asarray(json.loads(user.face_embedding), dtype=np.float32)
            cv_pipeline.known_embeddings[user.id] = embedding
            cv_pipeline.known_users[user.id] = {
                "name": user.name,
                "employee_id": user.employee_id,
            }
        except (TypeError, ValueError, json.JSONDecodeError):
            continue


@router.get("/health", include_in_schema=False)
async def health(db: Session = Depends(get_db)):
    """Health check endpoint."""
    load_database_embeddings(db)
    system_status = cv_pipeline.get_system_status()
    return {
        "status": "healthy",
        "service": "attendance-api",
        "known_users": system_status["known_users_count"],
        "pipeline_ready": system_status["pipeline_ready"],
    }


@router.post("/analyze", response_model=dict)
async def analyze_frame(face_image: UploadFile = File(...), db: Session = Depends(get_db)):
    """Detect faces in a frame and match each one against registered embeddings."""
    import cv2
    import numpy as np

    contents = await face_image.read()
    image = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not decode face image")
    load_database_embeddings(db)
    return {"faces": cv_pipeline.analyze_faces(image)}


@router.post("/registration-check", response_model=dict)
async def registration_check(
    face_image: UploadFile = File(...), _admin: str = Depends(require_admin)
):
    """Validate one enrollment frame before advancing to the next angle."""
    import cv2

    contents = await face_image.read()
    image = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image could not be decoded")
    boxes = cv_pipeline.detect_face_boxes(image)
    face_count = len(boxes)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(gray))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    valid = bool(face_count >= 1 or (brightness > 25 and sharpness > 15))
    return {
        "valid": valid,
        "face_count": face_count,
        "message": (
            "Face is clear"
            if valid
            else "Move closer, improve lighting, and keep your face inside the frame"
        ),
    }


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register_user(
    name: str,
    employee_id: str,
    face_images: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
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

    if len(face_images) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Capture at least five face images: center, left, right, up, and down",
        )

    # Require one detectable face per angle, then average normalized vectors.
    embeddings = []
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

        embedding = cv_pipeline.extract_single_face_embedding(img)
        if embedding is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image {i + 1} must contain exactly one clearly visible face",
            )
        embeddings.append(embedding)

    # Create user in database
    new_user = User(name=name, employee_id=employee_id)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    embedding = np.mean(np.stack(embeddings), axis=0)
    embedding /= np.linalg.norm(embedding)
    new_user.face_embedding = json.dumps(embedding.tolist())
    cv_pipeline.known_embeddings[new_user.id] = embedding
    cv_pipeline.known_users[new_user.id] = {"name": name, "employee_id": employee_id}
    db.commit()

    return {
        "user_id": new_user.id,
        "name": new_user.name,
        "employee_id": new_user.employee_id,
        "embedding_dimension": len(embedding) if embedding is not None else 0,
        "captured_angles": len(embeddings),
        "message": f"Employee {name} registered successfully",
    }


@router.post("/clock-in", response_model=dict)
async def clock_in(
    employee_id: str,
    face_image: UploadFile = File(...),
    face_images: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    """
    Clock in for an employee.

    - **employee_id**: Employee identifier
    - **face_image**: Live face image from camera feed
    """
    # Read the primary frame and optional movement frames used for liveness.
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

    liveness_frames = [img]
    for uploaded_frame in face_images:
        frame_contents = await uploaded_frame.read()
        frame_array = np.frombuffer(frame_contents, np.uint8)
        frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
        if frame is not None:
            liveness_frames.append(frame)
    if len(liveness_frames) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Liveness check requires three camera frames. Move your head slightly and try again.",
        )
    is_live, liveness_score = cv_pipeline.check_liveness(liveness_frames)
    if not is_live:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Liveness check failed. Move your head slightly while facing the camera.",
        )

    # Check if employee exists in DB
    from sqlalchemy import select
    from datetime import datetime, timedelta, timezone
    result = db.execute(select(User).where(User.employee_id == employee_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found in database",
        )
    # Match the requested employee against each detected face. This makes
    # attendance safe when several people are visible in the same frame.
    user_id = None
    confidence = None
    detected_boxes = cv_pipeline.detect_face_boxes(img)
    for x, y, width, height in detected_boxes:
        face_crop = img[y : y + height, x : x + width]
        matched_id, matched_confidence, _ = cv_pipeline.verify_face(face_crop)
        if matched_id == user.id:
            user_id = matched_id
            confidence = matched_confidence
            break
    if user_id is None and not detected_boxes:
        user_id, confidence, _ = cv_pipeline.verify_face(img)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The requested employee was not recognized in the camera frame",
        )

    # Attendance is idempotent for one employee for one hour.
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_result = db.execute(
        select(AttendanceLog)
        .where(
            AttendanceLog.user_id == user.id,
            AttendanceLog.clock_in.isnot(None),
            AttendanceLog.clock_in >= cutoff,
        )
        .order_by(AttendanceLog.clock_in.desc())
    )
    recent_log = recent_result.scalars().first()
    if recent_log is not None:
        return {
            "log_id": recent_log.id,
            "user_id": user.id,
            "employee_id": user.employee_id,
            "name": user.name,
            "clock_in": recent_log.clock_in.isoformat() if recent_log.clock_in else None,
            "confidence": round(recent_log.confidence, 4),
            "already_marked": True,
            "message": f"Attendance already marked for {user.name} within the last hour",
        }

    # Record attendance log
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
        "liveness_score": round(liveness_score, 4),
        "already_marked": False,
        "message": f"Clock-in successful for {user.name}",
    }


@router.post("/clock-out", response_model=dict)
async def clock_out(
    employee_id: str,
    db: Session = Depends(get_db),
):
    """Clock out an employee's most recent open attendance log."""
    from datetime import datetime, timezone
    from sqlalchemy import select

    user_result = db.execute(select(User).where(User.employee_id == employee_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    log_result = db.execute(
        select(AttendanceLog)
        .where(AttendanceLog.user_id == user.id, AttendanceLog.clock_out.is_(None))
        .order_by(AttendanceLog.clock_in.desc())
    )
    log = log_result.scalars().first()
    if log is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No open attendance log")

    log.clock_out = datetime.now(timezone.utc)
    db.commit()
    db.refresh(log)
    return {
        "log_id": log.id,
        "user_id": user.id,
        "employee_id": user.employee_id,
        "name": user.name,
        "clock_out": log.clock_out.isoformat(),
        "message": f"Clock-out successful for {user.name}",
    }


@router.get("/logs", response_model=List[dict])
async def get_attendance_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """Retrieve attendance logs with pagination."""
    from sqlalchemy import select, desc
    result = db.execute(
        select(AttendanceLog, User)
        .join(User, User.id == AttendanceLog.user_id)
        .order_by(desc(AttendanceLog.created_at))
        .offset(skip)
        .limit(limit)
    )
    logs = result.all()

    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "employee_id": user.employee_id,
            "name": user.name,
            "clock_in": log.clock_in.isoformat() if log.clock_in else None,
            "clock_out": log.clock_out.isoformat() if log.clock_out else None,
            "confidence": log.confidence,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log, user in logs
    ]


@router.get("/users", response_model=List[dict])
async def get_registered_users(
    db: Session = Depends(get_db), _admin: str = Depends(require_admin)
):
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
    _admin: str = Depends(require_admin),
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
    cv_pipeline.known_embeddings.pop(user_id, None)
    cv_pipeline.known_users.pop(user_id, None)

    return None


@router.get("/logs/export")
async def export_attendance_logs(
    db: Session = Depends(get_db), _admin: str = Depends(require_admin)
):
    """Export attendance details as an Excel-compatible CSV file."""
    from sqlalchemy import select, desc

    rows = db.execute(
        select(AttendanceLog, User)
        .join(User, User.id == AttendanceLog.user_id)
        .order_by(desc(AttendanceLog.created_at))
    ).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Log ID", "Employee ID", "Name", "Clock In", "Clock Out", "Confidence"])
    for log, user in rows:
        writer.writerow([
            log.id, user.employee_id, user.name, log.clock_in, log.clock_out,
            f"{log.confidence:.4f}",
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance-report.csv"},
    )