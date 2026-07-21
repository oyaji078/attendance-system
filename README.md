# Attendance System

Face-recognition attendance kiosk. FastAPI + PostgreSQL/pgvector + Redis + InsightFace, with a static kiosk UI served by the API.

---

## Requirements

- Windows PowerShell
- Docker Desktop (running)
- Python 3.11+

Run every command from the project folder:

```powershell
cd D:\cnn\attendance-system
```

> All commands use `powershell -ExecutionPolicy Bypass -File` because Windows blocks `.ps1` scripts by default.

---

## 1. First-time setup

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-dev.ps1
```

This creates `.env`, sets up the Python environment, and prepares Docker.

---

## 2. Run locally

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

Wait until it prints the URLs, then open:

| What | URL |
|------|-----|
| **App (kiosk + admin)** | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |

The API serves the kiosk UI, so **one URL runs everything**.

Stop it:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-dev.ps1
```

---

## 3. Test on your phone (HTTPS tunnel)

The phone camera needs HTTPS, so use a tunnel. Keep the app running (step 2) in one window, then in a second window:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\tunnel-cloudflare.ps1 -Port 8000
```

It prints a URL like `https://something.trycloudflare.com`. **Open that URL on your phone** — kiosk and API both work through it (single origin, no extra setup).

First time only, install the tunnel tool:

```powershell
winget install Cloudflare.cloudflared
```

Stop the tunnel with `Ctrl+C`, or:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-tunnel.ps1
```

> Only the app port (8000) is tunneled. Never tunnel PostgreSQL, Redis, or Adminer.

---

## Admin login

Default account (change it after first login):

- Username: `admin`
- Password: `admin-local-1234`

Forgot the password? Reset it:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reset-admin-password.ps1 -Username admin
```

---

## Using the app

1. **Admin → Dosen / Kelas** — add lecturers and classes. Leave the *code* field blank and it auto-fills (`DSN-0001`, `KLS-0001`).
2. **Admin → Sesi Absensi** — create a session for a class.
   - Leave *Jam Mulai/Selesai* and *Hari Aktif* blank → the session is **always active**.
   - Fill them in → the session is only active during that WITA time window.
3. **Daftarkan Wajah** — enroll a student's face (4 poses).
4. **Mode Absensi** — pick the class/session (auto-selected when there's only one), face the camera, confirm. Attendance is recorded.

---

## Database browser (Adminer)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\db-browser.ps1
```

Open http://localhost:8081 and log in:

| Field | Value |
|-------|-------|
| System | PostgreSQL |
| Server | `postgres` |
| Username | `attendance` |
| Password | `attendance` |
| Database | `attendance` |

---

## Handy commands

| Task | Command |
|------|---------|
| Start app only, no dev kiosk server | `.\scripts\start-dev.ps1 -NoFrontend` |
| Restart the API | `.\scripts\restart-api.ps1` |
| Run migrations | `.\scripts\migrate.ps1` |
| Backup the database | `.\scripts\backup-db.ps1` |
| Schedule daily backups | `.\scripts\schedule-backup.ps1` (run as admin) |
| Reset admin password | `.\scripts\reset-admin-password.ps1 -Username admin` |
| Database shell | `.\scripts\db-shell.ps1` |
| Show this PC's LAN IP | `.\scripts\show-local-ip.ps1` |

(Prefix each with `powershell -ExecutionPolicy Bypass -File`.)

---

## Troubleshooting

**"running scripts is disabled on this system"** — use the bypass form shown above.

**Port 8000 already in use** — an old server is still running. Stop it, then restart:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-dev.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

**PostgreSQL / Redis connection error** — check Docker is up:

```powershell
docker ps
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

**No class shows in Mode Absensi** — you need an *active* attendance session for that class (Admin → Sesi Absensi). A session with a past time window won't appear.

**Camera blocked on phone** — you must open the **HTTPS tunnel URL** (step 3), not a plain `http://` LAN address.

---

## Configuration

Local defaults live in `.env` (created from `.env.example`):

```text
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=attendance
POSTGRES_USER=attendance
POSTGRES_PASSWORD=attendance
REDIS_URL=redis://127.0.0.1:6379/0
RECOGNITION_WARMUP_ON_STARTUP=true
```

Keep `RECOGNITION_WARMUP_ON_STARTUP=true` so the first scan is fast (otherwise the first request loads the model and takes ~20s).
