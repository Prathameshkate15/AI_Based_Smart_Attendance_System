# Smart Attendance Management System - API Specification

## Base URL
`http://localhost:8000/api/v1`

## Authentication
Currently no authentication middleware is enforced (development mode).
In production, add JWT/OAuth2 Bearer tokens via `Authorization: Bearer <token>` header.

## Error Responses
All errors return JSON with `detail` field:
```json
{
  "detail": "Error description"
}
```

HTTP status codes:
- **400** - Bad request (invalid input, liveness failure)
- **401** - Unauthorized (not registered, face not recognized)
- **403** - Forbidden (access denied - RBAC)
- **404** - Not found (user not in database)
- **409** - Conflict (employee ID already registered)
- **422** - Validation error
- **500** - Internal server error

---

## Endpoints

### GET /
**Root endpoint** - Welcome message and system status

| Field | Type | Description |
|-------|------|-------------|
| `message` | `str` | Welcome message |
| `version` | `str` | API version ("0.1.0") |
| `status` | `str` | System status ("operational") |

**Example response:**
```json
{
  "message": "Smart Attendance Management System API",
  "version": "0.1.0",
  "status": "operational"
}
```

---

### GET /health
**Health check endpoint** - Returns service health status. Bypasses API v1 prefix.

| Field | Type | Description |
|-------|------|-------------|
| `status` | `str` | "healthy" or "unhealthy" |
| `service` | `str` | "attendance-api" |
| `known_users` | `int` | Number of registered users (from CV pipeline) |

**Example response:**
```json
{
  "status": "healthy",
  "service": "attendance-api",
  "known_users": 3
}
```

---

### POST /register
**Register a new employee** with biometric data.

**Request Body:**
```json
{
  "name": "John Doe",
  "employee_id": "EMP-001",
  "face_images": [base64_encoded_images]  // 5-10 images as base64 strings
}
```

**Response (201 Created):**
```json
{
  "user_id": 1,
  "name": "John Doe",
  "employee_id": "EMP-001",
  "embedding_dimension": 512,
  "message": "Employee John Doe registered successfully"
}
```

**Errors:**
- **409** - "Employee ID already registered"

---

### POST /clock-in
**Clock in for an employee** via face verification.

### POST /clock-out
**Clock out an employee's most recent open attendance log.**

Query parameter:
- `employee_id` - registered employee identifier

**Response (200 OK):**
```json
{
  "log_id": 1,
  "employee_id": "EMP-001",
  "name": "John Doe",
  "clock_out": "2026-09-14T17:30:00+00:00",
  "message": "Clock-out successful for John Doe"
}
```

**Request Body:**
```json
{
  "employee_id": "EMP-001",
  "face_image": "base64_encoded_frame"  // Live camera frame
}
```

**Response (200 OK):**
```json
{
  "log_id": 1,
  "user_id": 1,
  "employee_id": "EMP-001",
  "name": "John Doe",
  "clock_in": "2026-09-13T08:30:00Z",
  "confidence": 0.94,
  "message": "Clock-in successful for John Doe"
}
```

**Errors:**
- **400** - "Liveness detection failed - possible photo spoof"
- **401** - "Face not recognized - employee not registered or face not matched"
- **404** - "Employee not found in database"

---

### GET /logs
**Retrieve attendance logs** with pagination.

**Query Parameters:**
- `skip` (int, default 0) - Number of records to skip
- `limit` (int, default 100) - Maximum records to return

**Response (200 OK):**
```json
{
  "logs": [
    {
      "id": 1,
      "user_id": 1,
      "employee_id": "EMP-001",
      "name": "John Doe",
      "clock_in": "2026-09-13T08:30:00Z",
      "clock_out": null,
      "confidence": 0.94,
      "created_at": "2026-09-13T08:30:15Z"
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 100
}
```

---

### GET /users
**List all registered users.**

**Response (200 OK):**
```json
{
  "users": [
    {
      "id": 1,
      "name": "John Doe",
      "employee_id": "EMP-001",
      "created_at": "2026-09-12T10:00:00Z"
    }
  ]
}
```

---

### DELETE /users/{user_id}
**Delete a user** and associated data.

**Path Parameters:**
- `user_id` (int) - User ID to delete

**Response (204 No Content):** Successful deletion with no body.

**Errors:**
- **404** - "User not found"

---

### Absenteeism Prediction (Internal/MLOps)

#### POST /ml/train
**Trigger model retraining** ( Celery task endpoint).

**Response:**
```json
{
  "status": "queued",
  "message": "Model retrain task queued for Monday 2AM UTC"
}
```

#### GET /ml/status
**Get MLflow model tracking status.**

**Response:**
```json
{
  "experiment": "absenteeism-prediction",
  "latest_run": {
    "run_id": "1234567890abcdef",
    "accuracy": 0.87,
    "trained_at": "2026-09-13T02:00:00Z"
  }
}
```

---

## Error Reference

| Error Code | Scenario |
|------------|----------|
| 400 | Liveness failure, invalid image format, bad request body |
| 401 | Face not recognized, employee not registered |
| 403 | Access denied (RBAC - not implemented in v0.1.0) |
| 404 | User not found, log not found |
| 409 | Employee ID already registered |
| 422 | Validation error (missing required fields) |
| 500 | Internal server error (MLflow, DB connection) |

---

## Versioning
- **Current version:** 0.1.0 (initial release)
- **API stability:** Experimental - may change between minor releases
- **Breaking changes:** Will be documented in CHANGELOG.md