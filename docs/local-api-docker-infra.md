# Local API + Docker Infra Mode

Mode ini menjalankan hanya service infrastruktur di Docker:

- PostgreSQL + pgvector lewat `pgvector/pgvector:pg16`
- Redis lewat `redis:7.4-alpine`
- API Python berjalan langsung di Windows dari venv `D:\PythonVenvs\attendance-api`
- Kiosk UI berjalan langsung di Windows sebagai static server
- Model berada di `D:\cnn\attendance-system\models`
- Data app berada di `D:\cnn\attendance-system\data`

Mode ini sengaja tidak menjalankan full Docker untuk API, migration, kiosk UI, atau kiosk agent. Docker hanya dipakai untuk Postgres dan Redis.

## Alasan

Mode ini lebih hemat storage lokal karena dependency Python tidak dibangun lagi ke image Docker API. Model InsightFace dan data app tetap berada di drive D project, bukan SSD eksternal. Setup ini juga lebih stabil dibanding menyimpan Docker storage di SSD eksternal, karena Docker Desktop tetap memakai lokasi storage aktif yang sudah dipindahkan ke `D:\DockerDesktopData\DockerDesktopWSL`.

Jangan gunakan SSD eksternal `E:` untuk model, Docker storage, venv, atau data project pada mode ini.

## Path Penting

- Project: `D:\cnn\attendance-system`
- Venv Python: `D:\PythonVenvs\attendance-api`
- Model root: `D:\cnn\attendance-system\models`
- InsightFace model root: `D:\cnn\attendance-system\models\insightface`
- Data root: `D:\cnn\attendance-system\data`
- Object storage lokal: `D:\cnn\attendance-system\data\object-storage`

Model InsightFace `buffalo_l` harus berada di `D:\cnn\attendance-system\models\insightface\models\buffalo_l`, atau mengikuti struktur yang sesuai dengan nilai `INSIGHTFACE_MODEL_ROOT` di `.env.local-api`.

## Menjalankan

Jalankan dari root project `D:\cnn\attendance-system`.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check-local-setup.ps1
powershell -ExecutionPolicy Bypass -File scripts/start-infra.ps1
powershell -ExecutionPolicy Bypass -File scripts/run-migrations-local.ps1
powershell -ExecutionPolicy Bypass -File scripts/start-api-local.ps1
powershell -ExecutionPolicy Bypass -File scripts/start-kiosk-local.ps1
```

`run-migrations-local.ps1` membutuhkan Postgres dari `start-infra.ps1` sudah berjalan.

## One-command local launcher

Untuk menjalankan seluruh mode lokal dari satu terminal, gunakan launcher berikut:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-project-local.ps1
```

Jika migration perlu dijalankan sebelum API dan kiosk dinyalakan:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-project-local.ps1 -RunMigrations
```

Cek status semua komponen:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/status-project-local.ps1
```

Stop semua komponen lokal dengan aman:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/stop-project-local.ps1
```

Restart semuanya:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/restart-project-local.ps1
```

Launcher ini tetap memakai Docker hanya untuk PostgreSQL dan Redis melalui `docker/docker-compose.infra.yml`. API dan Kiosk berjalan di background sebagai proses lokal Windows, sehingga tidak perlu membuka dua terminal terpisah. Log runtime ditulis ke `logs/`, sementara PID file disimpan di `.runtime/` agar proses bisa dicek dan dihentikan dengan bersih.

Launcher ini tidak menjalankan full Docker compose, tidak build image, tidak menghapus volume, dan tidak menjalankan prune.

## URL

- API: http://localhost:8000
- API health check: http://localhost:8000/health
- Kiosk UI: http://localhost:8080

## Admin Login Lokal

Admin dibuat otomatis saat API start jika tabel `admin_users` masih kosong. Nilai bootstrap dibaca dari `.env.local-api`:

```text
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=admin-local-1234
AUTH_SECRET_KEY=attendance-local-dev-change-this
```

Ganti password dan secret tersebut sebelum dipakai di lingkungan selain lokal. Halaman admin dan endpoint `/admin/*` serta `/enroll/*` membutuhkan cookie login admin. Halaman absensi publik tetap dapat memakai `/recognize` dan `/attendance/checkin` tanpa login.

## Melengkapi Model InsightFace Buffalo_l

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

Script download akan meminta konfirmasi sebelum mengunduh karena ukuran model cukup besar. Target download tetap di `D:\cnn\attendance-system\models\insightface`; model tidak disimpan di `E:` dan tidak memakai cache default di drive `C`.

Folder `models` tetap berada di drive D dan tidak masuk Git. `.gitignore` sudah mengabaikan `models/*` dan file model besar seperti `.onnx`, `.pt`, `.pth`, `.bin`, `.safetensors`, dan `.gguf`, tetapi tetap mengizinkan `models/.gitkeep`.

InsightFace `buffalo_l` adalah model pretrained. Tidak perlu dataset training besar untuk menjalankan inference. Yang dibutuhkan untuk penggunaan aplikasi adalah foto enrollment atau foto referensi wajah untuk data orang yang akan dikenali.

## Catatan Docker

Compose infra ada di `docker/docker-compose.infra.yml` dan hanya berisi `postgres` serta `redis`.

Jangan menjalankan compose full `docker/docker-compose.yml` kecuali memang ingin mode full Docker. Untuk mode hemat storage ini, gunakan script `scripts/start-infra.ps1` dan `scripts/stop-infra.ps1`.

`scripts/stop-infra.ps1` hanya menjalankan `docker compose stop`. Script ini tidak memakai `down -v` dan tidak menghapus volume.
