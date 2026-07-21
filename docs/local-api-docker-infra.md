# Local API + Docker Infra Mode

Mode ini menjalankan hanya service infrastruktur di Docker:

- PostgreSQL + pgvector melalui `pgvector/pgvector:pg16`
- Redis melalui `redis:7.4-alpine`
- API Python berjalan langsung di Windows
- Kiosk UI berjalan langsung di Windows sebagai static server
- Model berada di `D:\cnn\attendance-system\models`
- Data app berada di `D:\cnn\attendance-system\data`

Mode ini tidak menjalankan full Docker untuk API, migration, kiosk UI, atau kiosk agent. Docker hanya dipakai untuk Postgres dan Redis.

## Path Penting

- Project: `D:\cnn\attendance-system`
- Model root: `D:\cnn\attendance-system\models`
- InsightFace model root: `D:\cnn\attendance-system\models\insightface`
- Data root: `D:\cnn\attendance-system\data`
- Object storage lokal: `D:\cnn\attendance-system\data\object-storage`
- Runtime PID files: `.runtime\`
- Logs: `logs\`

Python dipilih otomatis dari urutan berikut:

1. Environment variable `ATTENDANCE_PYTHON`
2. `.venv\Scripts\python.exe`
3. `D:\PythonVenvs\attendance-api\Scripts\python.exe`
4. `python` dari PATH

## Menjalankan

Jalankan dari root project `D:\cnn\attendance-system`.

First-time setup:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-dev.ps1
```

Start local development stack:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-dev.ps1
```

Stop API dan kiosk, tetapi biarkan Postgres/Redis tetap berjalan:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/stop-dev.ps1
```

Stop semuanya termasuk Postgres dan Redis:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/stop-dev.ps1 -StopDocker
```

Restart API dan jalankan migration:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/restart-api.ps1
```

Jalankan migration saja:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/migrate.ps1
```

Launcher ini tetap memakai Docker hanya untuk PostgreSQL dan Redis melalui `docker/docker-compose.infra.yml`. API dan kiosk berjalan di background sebagai proses lokal Windows, sehingga tidak perlu membuka dua terminal terpisah.

## URL

- API: http://localhost:8000
- API health check: http://localhost:8000/health
- OpenAPI: http://localhost:8000/docs
- Kiosk UI: http://localhost:8080
- DB browser: http://localhost:8081 setelah menjalankan `scripts/db-browser.ps1`

## Database Browser

```powershell
powershell -ExecutionPolicy Bypass -File scripts/db-browser.ps1
```

Adminer login:

```text
System: PostgreSQL
Server: host.docker.internal:5432
Username: attendance
Password: attendance
Database: attendance
```

Jika `host.docker.internal` tidak berhasil, gunakan `docker-postgres-1` saat Adminer berjalan di network Docker yang sama.

## Shell Helpers

PostgreSQL:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/db-shell.ps1
```

Redis:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/redis-shell.ps1
```

## Admin Login Lokal

Admin dibuat otomatis saat API start jika tabel `admin_users` masih kosong. Nilai bootstrap dibaca dari `.env.local-api`:

```text
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=admin-local-1234
AUTH_SECRET_KEY=attendance-local-dev-change-this-minimum-32
```

Ganti password dan secret tersebut sebelum dipakai di lingkungan selain lokal. Endpoint `/admin/*` dan `/enroll/*` membutuhkan cookie login admin. Halaman absensi publik tetap dapat memakai flow kiosk tanpa login admin.

## Model InsightFace Buffalo_l

Model wajib berada di:

```text
D:\cnn\attendance-system\models\insightface\models\buffalo_l
```

File ONNX yang diharapkan:

- `1k3d68.onnx`
- `2d106det.onnx`
- `det_10g.onnx`
- `genderage.onnx`
- `w600k_r50.onnx`

Cek status model:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check-insightface-model.ps1
```

Download model jika belum ada:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download-insightface-buffalo-l.ps1
```

## Backup Dan Cleanup

Buat backup database:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/backup-db.ps1
```

Dry-run cleanup face data:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/cleanup-face-data.ps1
```

Execute cleanup face data hanya setelah review dry-run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/cleanup-face-data.ps1 -Execute -BackupFirst
```

Archive report lama:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/cleanup-reports.ps1 -Archive
```

## Catatan Docker

Compose infra ada di `docker/docker-compose.infra.yml` dan hanya berisi `postgres` serta `redis`.

Jangan menjalankan compose full `docker/docker-compose.yml` kecuali memang ingin mode full Docker. Untuk mode hemat storage ini, gunakan `scripts/start-dev.ps1` dan `scripts/stop-dev.ps1`.

`scripts/stop-dev.ps1` default tidak menghentikan Docker infra. Gunakan `-StopDocker` jika ingin menghentikan PostgreSQL dan Redis.
