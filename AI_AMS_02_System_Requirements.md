# AI System Requirements & Tech Stack

## 1. Core AI/ML Functional Requirements
* **Biometric Registration (Onboarding):**
  * Capture 5-10 images of a new employee, extract facial embeddings, and store them in a Vector Database.
* **Real-Time Inference (Clock-In/Out):**
  * **Face Detection:** Locate faces in a live video stream.
  * **Liveness Detection:** Verify the face is a real, live human (detecting blinking, head movement, or using depth estimation).
  * **Face Recognition:** Compare the live embedding against the Vector DB using Cosine Similarity or L2 distance.
* **Data Science & Analytics:**
  * **Anomaly Detection:** Flag unusual clock-in times or durations using algorithms like Isolation Forest.
  * **Predictive Modeling:** Train a classifier to predict the likelihood of future absenteeism based on weather, day of the week, and historical patterns.

## 2. Non-Functional Requirements
* **Inference Latency:** Face recognition pipeline must execute in < 500ms per frame to ensure a smooth user experience.
* **Privacy & Security:** Face images are *never* saved permanently; only mathematical embeddings (vectors) are stored to comply with biometric data regulations.
* **Scalability:** The vector search must remain fast even with 10,000+ registered users.

## 3. Technology Stack (Python / Data Science Heavy)

### AI & Machine Learning
* **OpenCV & dlib:** Image processing and basic face detection.
* **DeepFace / InsightFace:** State-of-the-art deep learning frameworks for extracting facial embeddings.
* **Scikit-Learn / XGBoost:** For training predictive models on tabular data (absenteeism forecasting, anomaly detection).
* **Pandas & NumPy:** Data wrangling and numerical operations.

### Backend & Inference Server
* **FastAPI:** Python web framework for building APIs (native async support, excellent for ML inference).
* **Uvicorn:** ASGI server to run FastAPI.
* **SQLAlchemy:** Python ORM for interacting with PostgreSQL.
* **Celery:** Asynchronous task queue for heavy batch processing (model retraining).

### Database Infrastructure
* **PostgreSQL:** Primary relational database (Users, Logs).
* **FAISS (Meta) or Milvus:** Vector database for indexing and querying face embeddings.
* **Redis:** Caching and message broker for Celery.

### MLOps & Ops
* **MLflow:** Model tracking and versioning.
* **Docker:** Containerizing the inference APIs and databases.
