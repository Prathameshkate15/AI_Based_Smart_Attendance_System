from sqlalchemy import Column, Integer, String, DateTime, Float, Text
from sqlalchemy.sql import func
from ..database import Base


class User(Base):
    """User model for registered employees."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    employee_id = Column(String(50), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AttendanceLog(Base):
    """Attendance log model for clock-in/out events."""
    __tablename__ = "attendance_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    clock_in = Column(DateTime(timezone=True))
    clock_out = Column(DateTime(timezone=True))
    confidence = Column(Float, nullable=False)  # CV confidence score
    frame_hash = Column(String(64), nullable=True)  # Hash of processed frame
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ModelVersion(Base):
    """ML model version tracking."""
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(100), nullable=False)
    version = Column(String(20), nullable=False)
    metrics = Column(Text, nullable=True)  # JSON string of accuracy/precision/recall
    is_active = Column(Integer, default=0)  # 1 if currently active, 0 otherwise
    created_at = Column(DateTime(timezone=True), server_default=func.now())