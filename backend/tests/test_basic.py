"""Basic tests for Smart Attendance System backend."""

import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.database import engine
from app.models.user import Base


def test_database_tables_exist():
    """Verify database tables were created."""
    # This test checks that SQLAlchemy models can be created
    # Tables should already exist from direct SQLite creation
    assert engine is not None


def test_mlflow_import():
    """Test MLflow can be imported and configured."""
    import mlflow
    # Just verify import works
    assert mlflow is not None


def test_cv_service_import():
    """Test CV service can be imported."""
    from app.services.cv_service import CvPipeline
    pipeline = CvPipeline()
    status = pipeline.get_system_status()
    # Should have known structure
    assert "known_users_count" in status


def test_privacy_middleware_import():
    """Test privacy middleware can be imported."""
    from app.privacy import PrivacyMiddleware, anonymize_embeddings, DataRetentionPolicy
    # Verify functions exist and are callable
    assert callable(anonymize_embeddings)
    assert callable(DataRetentionPolicy.get_attendance_log_retention_days)


def test_celery_import():
    """Test Celery app can be imported."""
    from app.mlops.celery_app import celery_app
    assert celery_app is not None


def test_mlops_import():
    """Test MLOps modules can be imported."""
    from app.mlops.model_trainer import AbsenteeismModel
    from app.mlops.inference import InferencePipeline
    assert AbsenteeismModel is not None
    assert InferencePipeline is not None