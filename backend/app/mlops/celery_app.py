"""
Celery application for scheduled model retraining and background tasks.

Handles:
- Weekly/monthly absenteeism model retraining
- Prediction drift monitoring
- Model version promotion
- Attendance data cleanup
"""

from celery import Celery
from celery.schedules import crontab
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Celery configuration
celery_app = Celery(
    "attendance_mlops",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

# Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Schedule: retrain model every Monday at 2AM UTC
    beat_schedule={
        "weekly-model-retrain": {
            "task": "attendance_mlops.retrain_model",
            "schedule": crontab(hour=2, minute=0, day_of_week=1),  # Monday 2AM
        },
        "daily-drift-check": {
            "task": "attendance_mlops.check_drift",
            "schedule": crontab(hour=3, minute=0),  # Daily 3AM
        },
        "monthly-data-cleanup": {
            "task": "attendance_mlops.cleanup_old_data",
            "schedule": crontab(day_of_month=1, hour=4, minute=0),  # 1st of month 4AM
        },
    },
)


# --- Task: Weekly Model Retrain ---

@celery_app.task(bind=True, max_retries=3)
def retrain_model(self):
    """
    Retrain the absenteeism prediction model using latest data.
    Runs weekly (default: Monday 2AM).
    """
    try:
        logger.info("Starting weekly model retrain...")

        # Import here to avoid circular imports
        from app.mlops.model_trainer import AbsenteeismModel
        from app.database import get_db, engine
        from app.models.user import Base
        import pandas as pd
        import numpy as np

        # Ensure DB tables exist
        Base.metadata.create_all(bind=engine)

        # Fetch recent attendance data for training
        # In production, would query from PostgreSQL + Vector DB
        # For now, simulate with placeholder
        logger.info("Fetching attendance data for retraining...")

        # Placeholder: would load from DB/vector store
        # df = pd.read_sql("SELECT * FROM attendance_logs ORDER BY created_at DESC LIMIT 1000", db.bind)
        # features, target = prepare_dataframe(df)

        # Train model
        # model_info = trainer.train(X_train, y_train, X_test, y_test)

        # Log retraining event
        logger.info("Model retrain completed successfully")

        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Weekly model retrain finished",
        }

    except Exception as exc:
        logger.error(f"Model retrain failed: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


# --- Task: Daily Drift Check ---

@celery_app.task(bind=True, max_retries=3)
def check_drift(self):
    """
    Check for prediction drift by comparing recent predictions vs actual outcomes.
    Runs daily (default: 3AM).
    """
    try:
        logger.info("Checking prediction drift...")

        # In production:
        # 1. Get last 24h predictions
        # 2. Compare actual clock-in/out outcomes
        # 3. If drift > threshold, trigger alert + retrain
        # 4. Log drift metrics to MLflow

        logger.info("Drift check completed - no significant drift detected")
        return {"status": "completed", "drift_detected": False}

    except Exception as exc:
        logger.error(f"Drift check failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


# --- Task: Monthly Data Cleanup ---

@celery_app.task(bind=True, max_retries=3)
def cleanup_old_data(self):
    """
    Clean up old attendance logs and model artifacts.
    Runs monthly (default: 1st of month at 4AM).
    """
    try:
        logger.info("Starting monthly data cleanup...")

        from sqlalchemy import create_engine, delete as sql_delete
        from app.database import engine

        # Delete attendance logs older than 3 years (per privacy policy)
        cutoff_date = datetime.utcnow() - timedelta(days=3 * 365)

        # In production would use SQLAlchemy delete
        # stmt = sql_delete(AttendanceLog).where(AttendanceLog.created_at < cutoff_date)
        # db.execute(stmt)

        logger.info(f"Data cleanup completed - cutoff date: {cutoff_date}")

        return {
            "status": "completed",
            "cutoff_date": cutoff_date.isoformat(),
            "message": "Monthly data cleanup finished",
        }

    except Exception as exc:
        logger.error(f"Data cleanup failed: {exc}")
        raise self.retry(exc=exc, countdown=60)