# Campus Face Recognition Attendance System

Production-oriented campus attendance monorepo for webcam enrollment, face-template recognition, and attendance logging.

## Architecture

- Python is the backend center.
- FastAPI is the API surface.
- InsightFace + ONNX Runtime provide detect/align/embed in the backend path.
- PostgreSQL + pgvector store embeddings.
- HNSW is created from day one on `face_templates.embedding`.
- Redis handles cooldown, recent-match cache, enrollment session state, and device heartbeat.
- Real-time matching queries `face_templates` only.
- `face_samples` are retained for enrollment history, audit, and template rebuild.
- Rust is limited to kiosk/local agent duties.
- New users become usable immediately after enrollment template build. No model retraining is required.

## Quick Start

1. For local non-Docker runs, copy `.env.example` to `.env`.
2. Start the full Docker stack:

```bash
docker compose -f docker/docker-compose.yml up --build
```

The compose path uses `docker/compose.env` and runs Alembic migrations before the API starts.

### Windows Docker setup on `D:`

If Docker Desktop is not installed yet, use the helper script below. It downloads the latest installer, installs Docker Desktop to `D:\DockerDesktop\app`, and places the WSL/containers data roots under `D:\DockerDesktop\...`.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-docker-desktop-d.ps1
```

After Docker Desktop finishes installing and reaches the `Running` state, bring the project stack up with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\docker-up.ps1
```

Use the kiosk agent profile when needed:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\docker-up.ps1 -EdgeProfile
```

## Key Endpoints

- `GET /devices/config/{device_code}`
- `POST /devices/heartbeat/{device_code}`
- `PUT /admin/devices/config/{device_code}`
- `POST /enroll/start`
- `POST /enroll/frame`
- `POST /enroll/finish`
- `POST /enroll/rebuild-template/{person_id}`
- `POST /recognize`
- `POST /attendance/checkin`
- `GET /attendance/status/{session_code}`
- `GET /attendance/logs/{session_code}`
- `GET /admin/attendance-sessions`
- `POST /admin/attendance-sessions`
- `GET /admin/attendance-sessions/{session_id}`
- `PUT /admin/attendance-sessions/{session_id}`
- `PATCH /admin/attendance-sessions/{session_id}/activate`
- `PATCH /admin/attendance-sessions/{session_id}/close`
- `POST /admin/reindex`
- `POST /admin/rebuild-all-templates`
- `GET /admin/metrics`
- `GET /admin/person/{student_id}`
