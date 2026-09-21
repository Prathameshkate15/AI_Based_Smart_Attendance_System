# Smart Attendance Management System\n\n## Project Overview\nA modern attendance tracking system using AI agentic capabilities for automated tracking, reporting, and insights.\n\n## Key Features\n- Biometric/face recognition attendance\n- Real-time dashboard\n- Automated reports\n- Leave management\n- Integration with HR systems\n\n## Technical Requirements\n- Python backend\n- React frontend\n- Database: PostgreSQL\n- AI/ML components for recognition\n- API endpoints\n\n## Agentic AI Enhancements\n- Intelligent scheduling agent\n- Anomaly detection for attendance patterns\n- Predictive analytics for absenteeism\n- Natural language interface for queries\n

## Attendance analytics API
The admin dashboard can consume the production analytics endpoints (all require
the same `Authorization: Bearer <token>` returned by `/api/v1/admin/login`):

- `GET /api/v1/admin/analytics/summary?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
  returns totals, open/completed logs, hours, daily trends, and per-employee
  metrics. Dates default to the previous 30 days through today.
- `POST /api/v1/admin/analytics/anomalies/detect` runs the persisted
  Isolation Forest/robust small-sample detector for the selected period.
- `GET /api/v1/admin/analytics/anomalies` lists logs marked `REQUIRES_REVIEW`.

Anomaly scores and reasons are stored on attendance logs, allowing HR to review
results without recomputing them. Unusual clock-in times and shift durations
are flagged while preserving existing clock-in/out behavior.\n\n## Agentic AI Enhancements\n- Intelligent scheduling agent\n- Anomaly detection for attendance patterns\n- Predictive analytics for absenteeism\n- Natural language interface for queries\n
