"""Attendance analytics and anomaly detection.

The service deliberately works from the existing attendance tables so it is
usable with SQLite in development and PostgreSQL in production.  Detection is
deterministic for a given set of logs and persists the review state on each log.
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session
from sklearn.ensemble import IsolationForest

from ..models.user import AttendanceLog, User


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def resolve_date_range(start_date: Optional[date], end_date: Optional[date]):
    end_date = end_date or date.today()
    start_date = start_date or (end_date - timedelta(days=30))
    if start_date > end_date:
        raise ValueError("start_date must not be after end_date")
    start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start_date, end_date, start, end


def _logs(db: Session, start: datetime, end: datetime):
    return db.execute(
        select(AttendanceLog, User)
        .join(User, User.id == AttendanceLog.user_id)
        .where(AttendanceLog.clock_in >= start, AttendanceLog.clock_in < end)
        .order_by(AttendanceLog.clock_in)
    ).all()


def detect_anomalies(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    persist: bool = True,
):
    """Detect unusual clock-in times and shift lengths with Isolation Forest.

    A small dataset cannot train a useful forest, so a transparent robust
    z-score fallback is used until at least five completed logs exist.
    """
    _, _, start, end = resolve_date_range(start_date, end_date)
    rows = _logs(db, start, end)
    candidates = []
    for log, user in rows:
        clock_in = _as_utc(log.clock_in)
        if clock_in is None:
            continue
        duration = None
        if log.clock_out:
            duration = max(0.0, (_as_utc(log.clock_out) - clock_in).total_seconds() / 3600)
        # Minutes since midnight captures both unusually early and late starts.
        candidates.append((log, user, [clock_in.hour * 60 + clock_in.minute, duration or 0.0], duration))

    if not candidates:
        return []
    values = np.asarray([item[2] for item in candidates], dtype=float)
    if len(candidates) >= 5:
        model = IsolationForest(
            n_estimators=100, contamination="auto", random_state=42
        ).fit(values)
        labels = model.predict(values)
        scores = -model.score_samples(values)
    else:
        # Robust baseline: median and MAD avoid a single outlier moving the mean.
        median = np.median(values, axis=0)
        mad = np.median(np.abs(values - median), axis=0)
        scale = np.where(mad < 1.0, 60.0, mad * 1.4826)
        robust = np.max(np.abs(values - median) / scale, axis=1)
        labels = np.where(robust >= 3.0, -1, 1)
        scores = robust / 3.0

    anomalies = []
    for (log, user, features, duration), label, score in zip(candidates, labels, scores):
        clock_minutes = features[0]
        reasons = []
        if clock_minutes < 7 * 60 or clock_minutes > 20 * 60:
            reasons.append("unusual clock-in time")
        if duration is not None and (duration < 1.0 or duration > 14.0):
            reasons.append("unusual shift duration")
        if label == -1 and not reasons:
            reasons.append("unusual attendance pattern")
        is_anomaly = label == -1 or bool(reasons)
        if persist:
            log.anomaly_status = "REQUIRES_REVIEW" if is_anomaly else "NORMAL"
            log.anomaly_score = round(float(score), 6)
            log.anomaly_reason = "; ".join(reasons) if is_anomaly else None
        if is_anomaly:
            anomalies.append({
                "log_id": log.id,
                "user_id": user.id,
                "employee_id": user.employee_id,
                "name": user.name,
                "clock_in": _as_utc(log.clock_in).isoformat(),
                "clock_out": _as_utc(log.clock_out).isoformat() if log.clock_out else None,
                "score": round(float(score), 6),
                "reason": "; ".join(reasons) or "unusual attendance pattern",
                "status": "REQUIRES_REVIEW",
            })
    if persist:
        db.commit()
    return anomalies


def build_summary(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    start_date, end_date, start, end = resolve_date_range(start_date, end_date)
    rows = _logs(db, start, end)
    daily = {}
    employees = {}
    total_hours = 0.0
    completed = 0
    confidence = []
    for log, user in rows:
        day = _as_utc(log.clock_in).date().isoformat()
        item = daily.setdefault(day, {"date": day, "present": 0, "completed": 0, "hours": 0.0})
        item["present"] += 1
        person = employees.setdefault(user.employee_id, {
            "employee_id": user.employee_id, "name": user.name,
            "days_present": 0, "completed_logs": 0, "hours": 0.0,
            "average_confidence": 0.0, "_confidence": [],
        })
        person["days_present"] += 1
        if log.confidence is not None:
            confidence.append(float(log.confidence))
            person["_confidence"].append(float(log.confidence))
        if log.clock_out:
            hours = max(0.0, (_as_utc(log.clock_out) - _as_utc(log.clock_in)).total_seconds() / 3600)
            total_hours += hours
            completed += 1
            item["completed"] += 1
            item["hours"] += hours
            person["completed_logs"] += 1
            person["hours"] += hours
    for item in daily.values():
        item["hours"] = round(item["hours"], 2)
    employee_list = []
    for person in employees.values():
        values = person.pop("_confidence")
        person["average_confidence"] = round(float(np.mean(values)), 4) if values else None
        person["hours"] = round(person["hours"], 2)
        employee_list.append(person)
    return {
        "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
        "total_logs": len(rows), "completed_logs": completed,
        "open_logs": len(rows) - completed,
        "unique_employees": len(employees),
        "total_hours": round(total_hours, 2),
        "average_confidence": round(float(np.mean(confidence)), 4) if confidence else None,
        "daily": list(daily.values()), "employees": employee_list,
    }
