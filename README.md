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
| **App (kios + konsol)** | http://localhost:8000 |
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

To start the app locally and open the Cloudflare tunnel in one step:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-local-and-tunnel.ps1
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

The app has two halves on one URL:

- **Kios** — the camera screens: Daftarkan Wajah, Mode Absensi.
- **Konsol Akademik** — everything else, behind the Admin login.

Switch between them with the mode buttons on the kiosk, and **Mode Kios** in the
console header.

### Konsol Akademik

```text
Dashboard

Akademik          Absensi              Sistem
- Siswa           - Absensi            - Pengguna
- Kelas           - Rekap              - Pengaturan
- Mata Pelajaran     - Per Mata Pelajaran
- Jadwal             - Per Kelas
```

The sidebar and header stay fixed; only the content column scrolls. Tables scroll
inside their own box with a sticky header — there is no pagination anywhere.

**Secondary row actions live in the ⋮ menu**, not as a row of buttons. Deleting is
always a soft delete (*Nonaktifkan* / *Aktifkan kembali*): attendance is history
and must survive a student leaving.

### Setting up a term

1. **Akademik → Siswa** — add students. One subject can be taught to many
   classes, so add each subject once.
2. **Siswa → ⋮ → Kelola Kelas** — place the student in a class. Moving them later
   closes the old enrollment and opens a new one, keeping the history.
3. **Akademik → Mata Pelajaran** — add subjects (`MAPEL-0001` auto-fills).
4. **Akademik → Jadwal** — the weekly timetable. Click an empty cell to add a
   schedule for that day and hour, or a filled one to edit it. A schedule is
   class + subject + teacher + period, and it carries *Jumlah Pertemuan* (default
   16) which drives the P1..Pn columns on the recap.
   Tick *Aktifkan absensi wajah* and the schedule gets its own kiosk session.

### Recording attendance

Face recognition is the source, and it now reaches the recap on its own:

```text
Jadwal aktif -> kamera -> dikenali -> divalidasi -> attendance_logs (audit)
                                                 -> attendance_records (H pada pertemuan)
                                                 -> rekap
```

The first confirmed scan of a lesson claims the earliest still-planned
pertemuan, dates it today and marks it *Terlaksana*; later scans in the same
lesson join that same pertemuan. A status a teacher set by hand (Sakit, Izin,
Alpa) is never overwritten by a later scan.

A jadwal with no pertemuan yet gets its full list created on the first scan, so
attendance is never silently dropped. A kiosk session that no jadwal owns is
resolved through its class — but only when a single subject fits (one jadwal, or
one whose day and hour cover the moment of the scan). If several could match, the
scan is left unattributed rather than filed against the wrong subject.

**Absensi → Tarik Absensi Wajah** replays past scans that never reached the
recap, grouping each session's scans by day so every teaching day claims its own
pertemuan. It never changes a record that already exists, so running it twice is
safe.

**Absensi** lists every recorded attendance with its source (Face Recognition or
Manual). Use **Koreksi Absensi** there when the camera missed someone or got a
match wrong — pick the schedule, pick the meeting, adjust, save. Corrections land
in the same ledger the recap reads.

### The two recaps

|  | Rekap Per Mata Pelajaran | Rekap Per Kelas |
|---|---|---|
| Shape | students × meetings | students × subjects |
| Cells | H / S / I / A | attendance % |
| Filters | Mapel, Kelas, Periode | Kelas, Periode |
| Use | the detailed presensi sheet | one glance across the class |

**Per Mata Pelajaran** is the formal sheet: P1..Pn with the real meeting dates in
the header, H/I/S/A totals, and the percentage. NISN and Nama stay pinned while
you scroll out to P16. Export **PDF** (landscape, with the legend), **Excel**, or
**Print**.

**Per Kelas** is a summary — one percentage per subject plus an average. It never
shows P1..Pn; that is the other recap's job.

Neither is editable: a recap is computed from attendance, so there is no
Tambah/Edit/Hapus Rekap anywhere.

### Attendance percentage

```text
Kehadiran % = Hadir / pertemuan yang sudah dilaksanakan x 100
```

Meetings that have not happened yet are hatched and are **not** counted as Alpa:
4 present out of 5 held meetings reads 80%, even when the term plans 16. A
subject with no held meeting at all shows `–`, not 0%.

Codes: `H` Hadir · `S` Sakit · `I` Izin · `A` Alpa

### Logo and exports

**Sistem → Pengaturan** takes a school logo (PNG or JPEG, up to 300 KB). It is
stored with the settings and printed on the letterhead of **every** exported
document — the presensi PDF and the rekap Excel — together with the school name.

### Teacher accounts

**Sistem → Pengguna → Tambah Akun**, role *Guru*, linked to a teacher record.
That account signs into the same console but sees only Dashboard, Jadwal,
Absensi and Rekap, and only for classes where it is the assigned teacher. A guru
can correct attendance but cannot create schedules, classes, or subjects.

---

## Database browser (Adminer)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\db-browser.ps1
```

Open http://localhost:8081 and log in:

| Field | Value |
|-------|-------|
| System | PostgreSQL |
| Server | `host.docker.internal:5432` |
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

**No class shows in Mode Absensi** — the class needs a schedule with *Aktifkan absensi wajah* ticked (Akademik → Jadwal). A schedule whose time window has passed won't appear.

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
REDIS_URL=redis://127.0.0.1:16379/0
RECOGNITION_WARMUP_ON_STARTUP=true
```

Keep `RECOGNITION_WARMUP_ON_STARTUP=true` so the first scan is fast (otherwise the first request loads the model and takes ~20s).

### Running behind a tunnel or reverse proxy

Session cookies are marked `Secure` automatically whenever the request arrives
over HTTPS (directly or via `X-Forwarded-Proto`), so the Cloudflare tunnel in
step 3 is safe with `APP_ENV=development`.

Rate limits are counted per client IP. Behind a proxy every request appears to
come from the proxy itself, which collapses them into one shared bucket — one
brute-forcer would lock everyone out. Set:

```text
TRUST_PROXY_HEADERS=true
```

to count against the first `X-Forwarded-For` hop instead. **Only enable this
when a proxy you control sets that header**: otherwise a client can forge it and
bypass the limit entirely.
