"""Tests for attendance analytics and anomaly persistence."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import AttendanceLog, User
from app.services.analytics import build_summary, detect_anomalies


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_summary_aggregates_hours_and_employees():
    db = _session()
    user = User(name="Ada", employee_id="E1")
    db.add(user)
    db.flush()
    start = datetime(2026, 1, 5, 9, tzinfo=timezone.utc)
    db.add(AttendanceLog(user_id=user.id, clock_in=start, clock_out=start + timedelta(hours=8), confidence=.91))
    db.commit()

    result = build_summary(db, start.date(), start.date())

    assert result["total_logs"] == 1
    assert result["completed_logs"] == 1
    assert result["total_hours"] == 8
    assert result["employees"][0]["employee_id"] == "E1"
    assert result["daily"][0]["completed"] == 1


def test_detector_persists_unusual_clock_in():
    db = _session()
    user = User(name="Ada", employee_id="E1")
    db.add(user)
    db.flush()
    when = datetime(2026, 1, 5, 3, 15, tzinfo=timezone.utc)
    log = AttendanceLog(user_id=user.id, clock_in=when, clock_out=when + timedelta(hours=8), confidence=.9)
    db.add(log)
    db.commit()

    anomalies = detect_anomalies(db, when.date(), when.date())

    db.refresh(log)
    assert len(anomalies) == 1
    assert log.anomaly_status == "REQUIRES_REVIEW"
    assert "clock-in" in log.anomaly_reason
