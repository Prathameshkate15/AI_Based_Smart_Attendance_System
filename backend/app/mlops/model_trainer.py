"""
Model Trainer for Absenteeism Prediction

Trains predictive models on historical attendance data using XGBoost/Scikit-Learn.
Logs metrics and artifacts to MLflow for tracking and versioning.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any

import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
import mlflow
import mlflow.xgboost


class AbsenteeismModel:
    """
    Trains and tracks absenteeism prediction models.
    """

    def __init__(
        self,
        experiment_name: "absenteeism-prediction",
        model_name: "absenteeism-xgb",
        tracking_uri: str = "sqlite:///./mlflow.db",
    ):
        self.experiment_name = experiment_name
        self.model_name = model_name
        self.mlflow_uri = tracking_uri

        # Setup MLflow
        mlflow.set_tracking_uri(self.mlflow_uri)
        mlflow.set_experiment(self.experiment_name)

    def prepare_data(
        self, df: pd.DataFrame, target_col: "absenteeism_hours"
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Prepare features and target for model training.

        Expected columns in df:
        - Weather conditions
        - Day of week
        - Season
        - Month
        - Employee ID
        - etc.
        - target: absenteeism_hours (continuous) or binary flag
        """
        # Feature engineering placeholder
        # In production, would encode categorical features, handle missing values, etc.
        feature_cols = [
            "weather_code",
            "day_of_week",
            "season",
            "month",
            "is_weekend",
            "temperature",
            "humidity",
        ]

        # Handle missing values
        df = df.fillna(df.median(numeric_only=True))

        X = df[feature_cols].values.astype(float)
        y = df[target_col].values.astype(float)

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=None
        )

        return X_train, X_test, y_train, y_test

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        run_name: str = None,
    ) -> Dict[str, Any]:
        """
        Train XGBoost model and log to MLflow.
        """
        with mlflow.start_run(run_name=run_name) as run:
            # Train XGBoost
            model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                objective="binary:logistic",
                eval_metric="logloss",
                random_state=42,
            )

            model.fit(
                X_train,
                y_train,
                eval_set=[(X_test, y_test)],
                early_stopping_rounds=10,
                verbose=False,
            )

            # Predict and evaluate
            y_pred = model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            precision, recall, f1, _ = precision_recall_fscore_support(
                y_test, y_pred, average="weighted"
            )

            # Log metrics to MLflow
            mlflow.log_metric("accuracy", accuracy)
            mlflow.log_metric("precision", precision)
            mlflow.log_metric("recall", recall)
            mlflow.log_metric("f1", f1)
            mlflow.log_param("n_estimators", 100)
            mlflow.log_param("max_depth", 6)
            mlflow.log_param("learning_rate", 0.1)

            # Log model artifact
            mlflow.xgboost.log_model(model, "xgboost-model")

            # Return metrics and model info
            return {
                "run_id": run.info.run_id,
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "model": model,
                "feature_importance": dict(
                    zip(
                        feature_cols,
                        model.feature_importances_.tolist(),
                    )
                ),
            }

    def register_model(
        self, model_name: str = "AbsenteeismModel", version_notes: str = ""
    ) -> str:
        """
        Register the latest model in MLflow model registry.
        Returns the model version string.
        """
        client = mlflow.tracking.MlflowClient(tracking_uri=self.mlflow_uri)

        # Get latest run
        experiments = client.search_experiments(
            experiment_ids=[mlflow.get_experiment_by_name(self.experiment_name).experiment_id]
        )

        runs = client.search_runs(
            experiment_ids=experiments[0].experiment_id,
            order_by=["attributes.start_time DESC"],
            max_results=1,
        )

        if len(runs) == 0:
            raise ValueError("No runs found to register")

        latest_run = runs[0]
        run_id = latest_run.info.run_id

        # Register model
        result = client.create_model_version(
            name=model_name,
            source=f"runs:/{run_id}/xgboost-model",
            run_id=run_id,
            tags=["trained", datetime.utcnow().strftime("%Y%m%d")],
        )

        # Add version notes if provided
        if version_notes:
            client.set_model_version_tag(
                model_name, result.version, "notes", version_notes
            )

        return f"{model_name} v{result.version} trained successfully"

    def get_latest_model(self) -> Any:
        """Retrieve the latest trained model from MLflow."""
        client = mlflow.tracking.MlflowClient(tracking_uri=self.mlflow_uri)

        experiments = client.search_experiments()
        if len(experiments) == 0:
            raise ValueError("No experiments found")

        runs = client.search_runs(
            experiment_ids=experiments[0].experiment_id,
            order_by=["attributes.start_time DESC"],
            max_results=1,
        )

        if len(runs) == 0:
            raise ValueError("No runs found")

        run_id = runs[0].info.run_id
        model = mlflow.xgboost.load_model(f"runs:/{run_id}/xgboost-model")
        return model