# AI Data Pipelines & System Workflows

## Workflow 1: Biometric Registration (Data Ingestion)
1. **Capture:** HR Admin uses the frontend to capture 5 distinct images of the new employee.
2. **Preprocessing:** Python backend receives images, standardizes lighting, aligns the face (centering the eyes), and crops.
3. **Feature Extraction:** Images are passed through a Convolutional Neural Network (CNN) (e.g., ResNet/ArcFace) to generate a 512-dimensional vector (embedding) representing the face.
4. **Vector Storage:** The embeddings are saved into the Vector Database (e.g., FAISS) tied to the `employee_id`, and tabular data is saved to PostgreSQL.

## Workflow 2: Automated Clock-In (Real-Time Inference)
1. **Stream:** Web kiosk streams live frames to the FastAPI backend via WebSockets.
2. **Detection & Liveness:** 
   * `OpenCV` detects a face in the frame.
   * A lightweight ML model checks for liveness (e.g., detecting micro-textures or spatial depth) to reject printed photos.
3. **Vector Search:** 
   * The live face is converted to an embedding.
   * The backend queries the Vector DB for the Nearest Neighbor (KNN) using Cosine Similarity.
4. **Threshold Check:** If the similarity score exceeds the confidence threshold (e.g., > 0.85), a "Match" is confirmed.
5. **Logging:** The backend logs a timestamp to PostgreSQL and returns a "Clocked In: Welcome, [Name]" event to the frontend.

## Workflow 3: Batch ML Processing (Predictive Analytics)
1. **Trigger:** A scheduled `Celery` task runs every Sunday at midnight.
2. **Data Extraction:** Extracts the last 6 months of attendance data from PostgreSQL into a Pandas DataFrame.
3. **Feature Engineering:** Creates features like `days_since_last_leave`, `average_weekly_hours`, `late_arrival_frequency`, and external data like `weather_forecast`.
4. **Model Inference:** Passes the data through an XGBoost classification model to generate an "Absenteeism Risk Score" (0 to 100%) for each employee for the upcoming week.
5. **Dashboard Update:** Saves these predictions to the database so the HR Admin Dashboard can highlight "High Risk" employees.

## Workflow 4: Anomaly Detection (Unsupervised Learning)
1. Following the daily clock-out, a Python script runs an Isolation Forest algorithm over the day's time logs.
2. It detects structural anomalies (e.g., an employee who usually works 9-to-5 suddenly logging in at 3 AM).
3. These records are flagged in the database as `REQUIRES_REVIEW` and an alert is generated for the HR team.
