# Attendance System

FastAPI, PostgreSQL + pgvector, Redis, and a static kiosk UI for face recognition attendance.

## Quick Start

### 1. Open PowerShell and go to the project folder

```powershell
cd D:\cnn\attendance-system
```

### 2. First-time setup

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-dev.ps1
```

### 3. Start the project

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

Wait for all services to start. You will see:
- API on port `8000`
- Kiosk UI on port `8080`

### 4. Open the app

| What | URL |
|------|-----|
| Kiosk UI (attendance) | http://localhost:8080 |
| API Docs (Swagger) | http://localhost:8000/docs |
| API JSON spec | http://localhost:8000/openapi.json |

### 5. Stop the project

Keep Docker running (recommended):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-dev.ps1
```

Stop everything including Docker:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-dev.ps1 -StopDocker
```

---

## Running Scripts on Windows

All commands above use `powershell -ExecutionPolicy Bypass -File` because Windows blocks `.ps1` scripts by default.

If your system allows scripts, you may run `.\scripts\start-dev.ps1` directly. If blocked, use the Bypass command shown above.

The bypass applies only to the current execution and does not change system policy.

---

## Features

- Public kiosk attendance with class/session selection
- Face recognition preview with manual confirmation
- Admin login and enrollment management
- Attendance session logs in WITA timezone
- PostgreSQL with pgvector and HNSW index
- Redis for cooldown, rate limiting, CSRF, and caching
- Liveness checks and quality gates
- Cloudflare/ngrok tunnel support for public access

## Requirements

- Windows PowerShell
- Docker Desktop
- Python 3.11 or newer

The kiosk UI is static HTML/CSS/JS and does not require `npm install`.

---

## Common Commands

All scripts run from the project root: `cd D:\cnn\attendance-system`

| Task | Command |
|------|---------|
| Start API only (no UI) | `powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1 -NoFrontend` |
| Restart API | `powershell -ExecutionPolicy Bypass -File .\scripts\restart-api.ps1` |
| Run migrations | `powershell -ExecutionPolicy Bypass -File .\scripts\migrate.ps1` |
| Database shell | `powershell -ExecutionPolicy Bypass -File .\scripts\db-shell.ps1` |
| Redis shell | `powershell -ExecutionPolicy Bypass -File .\scripts\redis-shell.ps1` |
| Database browser (Adminer) | `powershell -ExecutionPolicy Bypass -File .\scripts\db-browser.ps1` |
| Backup database | `powershell -ExecutionPolicy Bypass -File .\scripts\backup-db.ps1` |

---

## Environment

Local development defaults:

```text
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=attendance
POSTGRES_USER=attendance
POSTGRES_PASSWORD=attendance
REDIS_URL=redis://127.0.0.1:6379/0
```

If `.env` is missing, `setup-dev.ps1` creates it from `.env.example`.

---

## Advanced Topics

### Tunnel / Public Access

Never tunnel PostgreSQL (5432), Redis (6379), or Adminer (8081). Only expose the kiosk UI and API.

#### Local LAN Access

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\show-local-ip.ps1
```

Open `http://LOCAL_IP:8080` from devices on the same Wi-Fi.

#### Cloudflare Tunnel

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\tunnel-cloudflare.ps1 -Target frontend
powershell -ExecutionPolicy Bypass -File .\scripts\tunnel-cloudflare.ps1 -Target api
```

Open the frontend URL with API parameter:
`https://FRONTEND.trycloudflare.com?api_base_url=https://API.trycloudflare.com`

Add the tunnel origin to `CORS_ALLOWED_ORIGINS` or `TRUSTED_TUNNEL_ORIGINS`, then restart the API.

#### ngrok Tunnel

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\tunnel-ngrok.ps1 -Port 8080
powershell -ExecutionPolicy Bypass -File .\scripts\tunnel-ngrok.ps1 -Port 8000
```

Use: `https://FRONTEND.ngrok-free.app?api_base_url=https://API.ngrok-free.app`

#### Tunnel Status and Stop

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\tunnel-status.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\stop-tunnel.ps1
```

#### Security Notes

- Do not expose Adminer publicly
- Admin pages require login cookies and CSRF
- Keep rate limiting and Redis cooldown enabled
- Use HTTPS tunnel URLs for camera access from phones

### Database Browser (Adminer)

Start Adminer:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\db-browser.ps1
```

Open http://localhost:8081 and login:

| Field | Value |
|-------|-------|
| System | PostgreSQL |
| Server | host.docker.internal:5432 |
| Username | attendance |
| Password | attendance |
| Database | attendance |

### Useful SQL

```sql
SELECT * FROM alembic_version;
SELECT session_code, session_name, class_id, is_active, repeat_days, start_time, end_time, timezone
FROM attendance_sessions ORDER BY created_at DESC LIMIT 20;
```

### Cleanup and Backups

Database backups are saved to `backups/attendance_YYYYMMDD_HHMMSS.dump`.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backup-db.ps1
```

Face data cleanup (dry-run first):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup-face-data.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup-face-data.ps1 -Execute -BackupFirst
```

Archive old reports:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup-reports.ps1 -Archive
```

### Full Docker Alternative

```powershell
docker compose -f docker/docker-compose.yml up --build
```

For the storage-saving local workflow, prefer the script-based start.

---

## Troubleshooting

### "running scripts is disabled on this system"

Use the bypass form for any script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\<script-name>.ps1
```

### 404 on /attendance/classes/active

API process is stale. Restart it:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\restart-api.ps1
```

### PostgreSQL or Redis connection error

```powershell
docker ps
docker logs docker-postgres-1
docker logs docker-redis-1
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1 -NoFrontend
```

### Port 8000 already in use

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
powershell -ExecutionPolicy Bypass -File .\scripts\restart-api.ps1
```

### Docker container exited

```powershell
docker ps -a
docker logs docker-postgres-1
docker logs docker-redis-1
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1 -NoFrontend
```

Browser extension console warnings are not project errors unless they reference `localhost:8000` or `localhost:8080`.
