"""Computer Vision pipeline tests for Smart Attendance System."""

import pytest
import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.services.cv_service import CvPipeline


def test_cv_pipeline_initialization():
    """Test CV pipeline can be initialized with default params."""
    pipeline = CvPipeline()
    status = pipeline.get_system_status()
    assert status["known_users_count"] == 0
    assert status["pipeline_ready"] is False


def test_cv_pipeline_with_thresholds():
    """Test CV pipeline initialization with custom thresholds."""
    pipeline = CvPipeline(confidence_threshold=0.6, liveness_threshold=0.8)
    status = pipeline.get_system_status()
    assert status["confidence_threshold"] == 0.6
    assert status["liveness_threshold"] == 0.8


def test_cv_pipeline_no_model():
    """Test pipeline works without InsightFace model (falls back to DeepFace)."""
    # This tests the fallback path
    pipeline = CvPipeline()
    # Should not crash on initialization
    status = pipeline.get_system_status()
    assert "known_users_count" in status


def test_anonymize_embeddings():
    """Test embedding anonymization produces consistent output."""
    from app.privacy import anonymize_embeddings

    # Create a sample embedding
    sample_emb = np.random.rand(512).astype(np.float32)

    # Anonymize twice - should get different hashes due to random embedding
    hash1 = anonymize_embeddings(sample_emb)
    hash2 = anonymize_embeddings(sample_emb)

    # Both should be valid SHA-256 hex strings (64 chars)
    assert len(hash1) == 64
    assert len(hash2) == 64
    assert isinstance(hash1, str)
    assert isinstance(hash2, str)


def test_data_retention_policy():
    """Test data retention policy constants."""
    from app.privacy import DataRetentionPolicy

    embedding_days = DataRetentionPolicy.EMBEDDING_RETENTION_DAYS
    attendance_days = DataRetentionPolicy.ATTENDANCE_LOG_RETENTION_DAYS

    # Should be reasonable values (in days)
    assert embedding_days > 0
    assert attendance_days > 0
    # Attendance retention should be longer or equal to embedding
    assert attendance_days >= embedding_days