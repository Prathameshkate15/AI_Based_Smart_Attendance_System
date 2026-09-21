# Smart Attendance Management System - Deployment Guide

## Prerequisites

### Software Requirements
- Docker (v20.10+) and Docker Compose (v2.0+)
- Git
- Python 3.11+ (for local development without Docker)
- Node.js v18+ and npm (for React frontend, or use Bun)
- Redis (for Celery broker/backed and FastAPI caching)
- PostgreSQL (optional - Docker included)
- MLflow tracking (included via Docker)

### Environment Variables
Create a `.env` file in the project root:

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/attendance

# Redis (Celery broker)
REDIS_URL=redis://localhost:6379/0

# Application
SECRET_KEY=your-secret-key-change-this-in-production
ENVIRONMENT=development  # or "production"

# Security
ENCRYPTION_KEY=base64-encoded-32-bytes-key-for-data-encryption
```

## Docker Compose Deployment

### 1. Start All Services
```bash
docker-compose up -d
```

This will start:
- **api** - FastAPI backend (port 8000)
- **frontend** - React app (port 3000)
- **postgres** - PostgreSQL database (port 5432)
- **redis** - Redis cache & Celery broker (port 6379)
- **vector-db** - FAISS/Milvus vector search (if configured)

### 2. Verify Services Are Running
```bash
# Check API health
curl http://localhost:8000/api/v1/health

# Check frontend
open http://localhost:3000

# Check PostgreSQL
psql -h localhost -U postgres -d attendance

# Check Redis
redis-cli ping
```

### 3. Access the Application
- **Backend API:** http://localhost:8000/api/v1
- **Frontend UI:** http://localhost:3000
- **API Documentation:** http://localhost:8000/api/docs (Swagger)
- **ReDoc:** http://localhost:8000/api/redoc

---

## Local Development (Without Docker)

### Backend Setup
```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Initialize database
cd backend
python -m alemic upgrade head  # or: python -c "from app.database import engine; from app.models.user import Base; Base.metadata.create_all(bind=engine)"

# 4. Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup
```bash
cd frontend
bun install  # or: npm install
bun run dev  # or: npm run dev
```

The frontend will proxy API calls to `http://localhost:8000/api/v1`.

---

## Production Checklist

### [ ] Database
- [ ] PostgreSQL configured with proper credentials
- [ ] SSL/TLS enabled for database connections
- [ ] Regular backups configured
- [ ] Connection pooling enabled

### [ ] Security
- [ ] `SECRET_KEY` set to strong random value
- [ ] `ENCRYPTION_KEY` configured for data-at-rest encryption
- [ ] CORS origins restricted to trusted domains
- [ ] HTTPS/TLS termination at load balancer
- [ ] Security headers enforced (already in middleware)
- [ ] Role-based access control implemented (planned for v0.2.0)

### [ ] MLOps
- [ ] MLflow tracking server configured (separate production deployment)
- [ ] Redis Celery broker running and scaled
- [ ] Model retraining schedule verified (weekly Mondays at 2AM UTC)
- [ ] Model version promotion process documented

### [ ] Monitoring
- [ ] Health checks configured ( /health endpoint )
- [ ] Log aggregation (structured JSON logs)
- [ ] Metrics collection (Prometheus + Grafana optional)
- [ ] Alerting for failed clock-ins, liveness rejections

### [ ] Compliance
- [ ] Data retention policy configured (3 years attendance logs, 1 year embeddings)
- [ ] GDPR/Rose compliance review completed
- [ ] Audit logging verified (all biometric access logged)
- [ ] Encryption-at-rest enabled

---

## Production Deployment Steps

## Public showcase: Vercel + Render

The repository includes `vercel.json` and `render.yaml` for a split showcase
deployment:

1. Push the repository to GitHub.
2. In Render, use **Blueprints** and select `render.yaml`.
3. Set `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_TOKEN_SECRET`, and
   `CORS_ORIGINS` in the Render service environment. Set `CORS_ORIGINS` to the
   final Vercel URL, for example
   `https://smart-attendance-showcase.vercel.app`.
4. Wait for the Render health check at
   `https://YOUR-API.onrender.com/api/v1/health` to return HTTP 200.
5. Import the same repository into Vercel with root directory `frontend`.
6. Set `VITE_API_BASE_URL` in Vercel to
   `https://YOUR-API.onrender.com/api/v1`.
7. Redeploy Vercel after setting the environment variable.

The Render blueprint provisions PostgreSQL and uses the backend Dockerfile.
Never use the development credentials or a wildcard CORS origin for a public
deployment. Browser camera access requires the deployed Vercel site to use
HTTPS.

### Step 1: Build Docker Images
```bash
docker-compose build
# Or build individually:
docker build -t smart-attendance-api ./backend
docker build -t smart-attendance-frontend ./frontend
```

### Step 2: Start Services
```bash
docker-compose up -d
```

### Step 3: Run Database Migrations
```bash
# If using PostgreSQL with Alembic
docker-compose exec api alembic upgrade head
# Or with direct SQL:
docker-compose exec api python -c "from app.database import engine; from app.models.user import Base; Base.metadata.create_all(bind=engine)"
```

### Step 4: Initialize Data (Optional)
```bash
# Seed with default admin user (or run via API)
docker-compose exec api python -c "
from app.database import SessionLocal
from app.models.user import User
from sqlalchemy import select

db = SessionLocal()
# Check if any users exist
stmt = select(User).limit(1)
result = db.execute(stmt)
if result.scalar_one_or_none() is None:
    admin = User(name='System Admin', employee_id='ADMIN-001')
    db.add(admin)
    db.commit()
    print('Default admin user created')
db.close()
"
```

### Step 5: Verify Deployment
```bash
# Health check
curl http://your-domain.com/api/v1/health

# Full system check
curl http://your-domain.com/
```

### Step 6: Set Up Monitoring
- Configure log rotation for Docker containers
- Set up alerting on failed health checks
- Monitor Redis and PostgreSQL performance
- Track MLflow experiment metrics

---

## Cloud Deployment (AWS / GCP / Azure)

### AWS Example
```bash
# ECS Fargate service for FastAPI
# RDS PostgreSQL instance
# ElastiCache Redis
# S3 for model artifacts and logs
# CloudFront for frontend distribution
```

### GCP Example
```bash
# Cloud Run for FastAPI service
# Cloud SQL for PostgreSQL
# MemoryStore for Redis
# Cloud Storage for artifacts
# Cloud CDN for frontend
```

### Azure Example
```bash
# Azure Container Apps for FastAPI
# Azure Database for PostgreSQL
# Azure Cache for Redis
# Azure Blob Storage for artifacts
# Azure Front Door for frontend
```

---

## Rollback Procedure

### If Deployment Fails
```bash
# Rollback Docker Compose
docker-compose down
docker-compose up -d  # This uses docker-compose.yml from git, which may be previous version

# Or explicitly rollback to previous version
docker tag smart-attendance-api:latest smart-attendance-api:previous
docker compose -f docker-compose.yml up -d smart-attendance-api
```

### If Database Migration Fails
```bash
# Rollback Alembic migration
docker compose exec api alembic downgrade head -1

# Or restore from backup
pg_dump postgresql://user:pass@host/db > backup.sql
psql postgresql://user:pass@host/db < backup_previous.sql
```

---

## Development Workflow

### Making Code Changes
1. Create a feature branch: `git checkout -b feature/xxxxx`
2. Make changes and test locally
3. Commit with descriptive message
4. Push to remote: `git push origin feature/xxxxx`
5. Create Pull Request
6. After PR approval: `git checkout main && git pull && docker-compose up -d --build`

### Running Tests
```bash
# Backend tests
cd backend
pytest tests/ -v

# Frontend tests (if configured)
cd frontend
npm test  # or: bun test
```

### Code Style
- Python: Black formatter, isort imports
- JavaScript/TypeScript: ESLint + Prettier
- Commit messages follow conventional commits format