# Kiosk Agent (Rust)

Agen kiosk headless: mengambil frame dari kamera atau berkas, menyaringnya dengan
pemeriksaan kecerahan/liveness sederhana, lalu mengirimkannya ke backend absensi.
Antrean lokal menahan frame saat jaringan putus dan mengirim ulang dengan backoff.

> **Status: bisa dibangun dan berjalan** sejak perbaikan 3 Agustus 2026 —
> `cargo build --release --features camera` menghasilkan biner 21,8 MB, dan
> `cargo test` lolos 10/10. Sebelumnya kode ini sama sekali tidak lolos
> kompilasi; rinciannya di [Riwayat perbaikan](#riwayat-perbaikan).
>
> Perlu dicatat, kiosk yang dipakai sehari-hari tetap **kiosk web** di
> `apps/kiosk-ui/`, yang mengakses kamera lewat
> `navigator.mediaDevices.getUserMedia` di browser. Agen ini belum dirujuk oleh
> skrip operasional mana pun.

---

## Di mana kode koneksi kamera

| Berkas | Fungsi | Peran |
|---|---|---|
| [`src/capture.rs`](src/capture.rs) | `open_camera` | **Membuka perangkat kamera** dan memulai stream |
| [`src/capture.rs`](src/capture.rs) | `CameraFrameSource::new` | Menyalakan thread kamera dan menunggu konfirmasi siap |
| [`src/capture.rs`](src/capture.rs) | `grab_jpeg` | Menarik satu frame dan memastikan hasilnya JPEG |
| [`src/config.rs`](src/config.rs) | `AgentConfig::from_env` | Memilih kamera vs berkas berdasarkan `CAMERA_INDEX` |
| [`src/capture.rs`](src/capture.rs) | `create_frame_source` | Pabrik yang dipanggil `main` |

Pembukaan perangkat memakai crate [`nokhwa`](https://crates.io/crates/nokhwa) 0.10:

```rust
let wanted = CameraFormat::new(
    Resolution::new(width.max(1), height.max(1)),
    FrameFormat::MJPEG,
    fps.clamp(1, 60),
);
let mut camera = nokhwa::Camera::new(
    CameraIndex::Index(index),                    // nomor perangkat, 0 = kamera pertama
    RequestedFormat::new::<RgbFormat>(RequestedFormatType::Closest(wanted)),
)?;
camera.open_stream()?;
```

`RequestedFormatType::Closest` membuat `CAMERA_WIDTH`, `CAMERA_HEIGHT`, dan
`CAMERA_FPS` benar-benar berpengaruh — ketiganya dicari yang paling mendekati
di antara format yang didukung perangkat.

### Kenapa kamera dijalankan di thread sendiri

`nokhwa::Camera` menyimpan `dyn CaptureBackendTrait` yang **bukan `Send` maupun
`Sync`**, sedangkan trait `FrameSource` mensyaratkan keduanya. Membungkusnya
dengan `Mutex` tidak menolong — kompiler tetap menolak, dan nilai seperti itu
juga tidak boleh dipegang melintasi titik `await`.

Solusinya: satu thread OS khusus (`kiosk-camera`) memiliki kamera dan tidak
pernah menyerahkannya keluar. Permintaan frame dikirim lewat
`tokio::sync::mpsc`, jawabannya kembali lewat `tokio::sync::oneshot`. Efek
sampingnya menguntungkan — panggilan driver yang memblokir tidak lagi
menduduki thread runtime async.

```
capture_frame()  ──oneshot::Sender──▶  thread "kiosk-camera"
      ▲                                   │  camera.frame()
      └────────── Result<Vec<u8>> ─────────┘  grab_jpeg()
```

Kode ini hanya ikut dikompilasi bila fitur `camera` diaktifkan:

```bash
cargo build --features camera
```

Tanpa fitur itu, `CAMERA_INDEX` diabaikan dengan peringatan dan agen jatuh ke
sumber berkas.

---

## Alur kerja

```
                   setiap HEARTBEAT_INTERVAL_SECONDS (default 10 detik)
                                    │
   ┌────────────────────────────────┼────────────────────────────────┐
   │                                │                                │
heartbeat()              capture_and_enqueue()              pop_ready() → recognize()
POST /devices/                  │                                     │
heartbeat/{code}         FrameSource                            gagal → push_back()
                                │                                (retry_count += 1)
                        average_brightness()                          │
                                │                                drop_stale()
                        heuristic_score() ≥ ambang?
                                │
                         base64 → LocalQueue
```

Saat menerima Ctrl-C / SIGTERM, `drain_queue` berusaha mengosongkan antrean
dengan tenggat total 5 detik dan batas 3 detik per permintaan.

---

## Rincian setiap berkas dan fungsi

### `src/main.rs` — orkestrator

| Fungsi | Tanda tangan | Penjelasan |
|---|---|---|
| `main` | `async fn main() -> Result<()>` | Titik masuk `#[tokio::main]`. Menyiapkan `tracing` dari `RUST_LOG`, memuat `AgentConfig::from_env()`, membangun `BackendClient`, membuat `FrameSource` (panik bila gagal), menyiapkan `LocalQueue`, lalu masuk `tokio::select!` antara detak interval dan sinyal berhenti. `MissedTickBehavior::Skip` mencegah detak menumpuk bila satu siklus kelewat lama. |
| `run_tick` | `async fn(&AgentConfig, &BackendClient, &dyn FrameSource, &mut LocalQueue)` | Satu siklus penuh: kirim heartbeat → tangkap & antrekan frame → kirim sampai `MAX_SENDS_PER_TICK` (8) item yang sudah lewat masa backoff → buang item basi. Kegagalan pengiriman mengembalikan item ke antrean lewat `push_back` lalu menghentikan siklus, agar backend yang baru saja gagal tidak dihujani permintaan. |
| `heartbeat` | `async fn(&BackendClient, &AgentConfig, usize)` | Menyusun `DeviceHeartbeat` berisi kode perangkat, versi dari `CARGO_PKG_VERSION`, kedalaman antrean sebenarnya, dan waktu RFC 3339. Kegagalan hanya dicatat, tidak menghentikan siklus. |
| `capture_and_enqueue` | `async fn(&AgentConfig, &dyn FrameSource, &mut LocalQueue)` | Melewati penangkapan bila antrean penuh. Mengambil frame, menghitung kecerahan rata-rata, menolak frame yang skor liveness-nya di bawah `LIVENESS_THRESHOLD` **sambil mencatatnya ke log**, lalu meng-encode base64 dan memasukkannya ke antrean sebagai `RecognizeRequest` berisi satu frame. |
| `drain_queue` | `async fn(&BackendClient, &mut LocalQueue)` | Pengosongan antrean saat mematikan agen. Berhenti pada tenggat 5 detik; tiap permintaan dibatasi 3 detik lewat `tokio::time::timeout`. |
| `shutdown_signal` | `async fn()` | Menunggu Ctrl-C; pada Unix juga menunggu SIGTERM. |

### `src/capture.rs` — sumber frame

| Item | Jenis | Penjelasan |
|---|---|---|
| `FrameSource` | trait | Kontrak tunggal `async fn capture_frame(&self) -> Result<Vec<u8>>`. Wajib `Send + Sync` agar bisa dipakai lintas task Tokio. |
| `FilesystemFrameSource` | struct | Membaca berkas gambar yang sama berulang kali — untuk pengembangan tanpa kamera. |
| `FilesystemFrameSource::new` | `fn(String) -> Self` | Menyimpan jalur berkas. |
| `impl FrameSource for FilesystemFrameSource` | — | `capture_frame` memanggil `tokio::fs::read`. |
| `CameraFrameSource` | struct | Menyimpan pengirim `tokio::sync::mpsc` menuju thread kamera. Hanya ada bila fitur `camera` aktif. |
| `CameraFrameSource::new` | `fn(u32, u32, u32, u32) -> Result<Self>` | Menyalakan thread `kiosk-camera`, menunggu jabat tangan kesiapan lewat `std::sync::mpsc`, lalu mengembalikan galat asli bila perangkat gagal dibuka. |
| `open_camera` | `fn(u32, u32, u32, u32) -> Result<nokhwa::Camera>` | **Membuka perangkat kamera** dengan `RequestedFormatType::Closest` — menghormati lebar, tinggi, dan fps — lalu memanggil `open_stream()`. Dijalankan di dalam thread kamera. |
| `grab_jpeg` | `fn(&mut nokhwa::Camera) -> Result<Vec<u8>>` | Menarik satu frame. Bila format sumbernya `FrameFormat::MJPEG`, buffer dikembalikan apa adanya (menghindari encode ulang yang memboroskan waktu dan kualitas); selain itu di-decode ke RGB8 lewat `decode_image_to_buffer` lalu di-encode ke JPEG. |
| `impl FrameSource for CameraFrameSource` | — | Mengirim `oneshot::Sender` ke thread kamera dan menunggu jawabannya. Tidak ada nilai non-`Send` yang melintasi `await`. |
| `FrameSourceKind` | enum | `Filesystem(String)` atau `Camera { index, width, height, fps }`. Varian kamera hanya ada bila fitur `camera` aktif. |
| `create_frame_source` | `fn(FrameSourceKind) -> Result<Box<dyn FrameSource>>` | Pabrik yang memetakan enum ke implementasi konkret. |

### `src/config.rs` — konfigurasi

| Item | Jenis | Penjelasan |
|---|---|---|
| `AgentConfig` | struct | 12 medan konfigurasi (lihat [tabel variabel lingkungan](#variabel-lingkungan)). |
| `env_or<T>` | `fn(&str, T) -> T` generik | Membaca variabel lingkungan dan mem-parsingnya; jika tidak ada atau gagal parsing, memakai nilai bawaan. Kesalahan parsing ditelan diam-diam. |
| `AgentConfig::from_env` | `fn() -> Self` | Menentukan sumber frame lebih dulu: bila `CAMERA_INDEX` terisi dan fitur `camera` aktif → varian kamera; bila fitur mati → peringatan lalu jatuh ke berkas; bila `CAMERA_INDEX` kosong → berkas. Sisanya diisi lewat `env_or`. |

### `src/client.rs` — klien HTTP

| Fungsi | Tanda tangan | Penjelasan |
|---|---|---|
| `BackendClient::new` | `fn(String, u64) -> Self` | Membangun `reqwest::Client` dengan tenggat waktu dan maksimal 2 koneksi menganggur per host. Panik bila klien gagal dibangun. |
| `heartbeat` | `async fn(&DeviceHeartbeat) -> Result<()>` | `POST {base}/devices/heartbeat/{device_code}`. `error_for_status()` mengubah status non-2xx jadi galat. |
| `recognize` | `async fn(&RecognizeRequest) -> Result<()>` | `POST {base}/recognize`. Respons tidak dibaca — agen hanya peduli berhasil atau tidak. |

Kedua endpoint sudah diverifikasi ada pada OpenAPI backend yang berjalan.

### `src/models.rs` — bentuk payload

| Struct | Medan |
|---|---|
| `DeviceHeartbeat` | `device_code`, `agent_version`, `queue_depth`, `captured_at` |
| `RecognitionFrame` | `frame_b64`, `pose_hint` (opsional) |
| `RecognizeRequest` | `device_code`, `frames`, `session_code` (opsional) |

### `src/quality.rs`

| Fungsi | Tanda tangan | Penjelasan |
|---|---|---|
| `average_brightness` | `fn(&[u8]) -> Option<f32>` | Men-decode gambar (format ditebak otomatis), mengubahnya ke luma 8-bit, lalu merata-ratakan seluruh piksel. Mengembalikan `None` bila decode gagal atau gambar kosong. |

### `src/liveness.rs`

| Fungsi | Tanda tangan | Penjelasan |
|---|---|---|
| `heuristic_score` | `fn(f32) -> f32` | Heuristik tiga tingkat: kecerahan < 20 → 0.20 (terlalu gelap), > 220 → 0.35 (terlalu terang), selebihnya → 0.75. Dengan ambang bawaan 0.70, hanya rentang tengah yang lolos. |

### `src/queue.rs` — antrean tahan-putus

| Item | Tanda tangan | Penjelasan |
|---|---|---|
| `QueueConfig` | struct | `max_size`, `base_backoff_ms`, `max_backoff_ms`, `max_retries`. `Default` = 128 / 1.000 ms / 60.000 ms / 10. |
| `QueuedItem` | struct | `request`, `retry_count`, `last_attempt_at`. |
| `LocalQueue::new` | `fn(QueueConfig) -> Self` | Mengalokasikan `VecDeque` sebesar kapasitas maksimum. |
| `push` | `fn(RecognizeRequest) -> bool` | Menambah item baru; `false` bila antrean penuh. |
| `push_back` | `fn(QueuedItem) -> bool` | Mengembalikan item yang gagal dikirim sambil menaikkan `retry_count`. `false` bila kuota percobaan habis atau antrean penuh — item dibuang. |
| `pop_ready` | `fn() -> Option<QueuedItem>` | Mengeluarkan item terdepan **hanya** bila masa backoff-nya sudah lewat. |
| `backoff_for` | `fn(u32) -> Duration` | `base_backoff_ms × 2^retry_count`, ditambah jitter acak dari rentang `[0, jeda/2)`, dibatasi `max_backoff_ms`. Jitter dilewati bila rentangnya kosong, sebab `fastrand` panik pada rentang nol. |
| `len` / `is_full` | `fn() -> usize` / `bool` | Kedalaman antrean dan status penuh. |
| `drop_stale` | `fn(Duration) -> usize` | Membuang item yang lebih tua dari batas umur; mengembalikan jumlah yang dibuang. |

Berisi 9 uji unit yang mencakup kapasitas, penambahan `retry_count`, penghormatan
backoff, dan pembuangan item basi.

---

## Variabel lingkungan

Salin `.env.example` lalu sesuaikan.

| Variabel | Bawaan | Keterangan |
|---|---|---|
| `BACKEND_BASE_URL` | `http://127.0.0.1:8000` | Alamat dasar API. |
| `DEVICE_CODE` | `gate-a01` | Harus cocok dengan `device_configs.device_code` di basis data. |
| `SESSION_CODE` | *(kosong)* | Kode sesi absensi; kosong berarti tidak dikirim. |
| `HEARTBEAT_INTERVAL_SECONDS` | `10` | Periode satu siklus penuh, bukan hanya heartbeat. |
| `SAMPLE_FRAME_PATH` | `./sample-frame.jpg` | Berkas yang dibaca dalam mode berkas. |
| `CAMERA_INDEX` | *(kosong)* | Diisi angka untuk memakai kamera. **Butuh fitur `camera`.** |
| `CAMERA_WIDTH` | `640` | Lebar yang diinginkan; dicari format terdekat yang didukung perangkat. |
| `CAMERA_HEIGHT` | `480` | Tinggi yang diinginkan; dicari format terdekat yang didukung perangkat. |
| `CAMERA_FPS` | `15` | Laju bingkai yang diinginkan, dijepit ke 1–60. |
| `LIVENESS_THRESHOLD` | `0.70` | Frame dengan skor di bawah ini dibuang tanpa dikirim. |
| `QUEUE_MAX_SIZE` | `128` | Kapasitas antrean. |
| `RETRY_BASE_BACKOFF_MS` | `1000` | Jeda dasar percobaan ulang. |
| `RETRY_MAX_BACKOFF_MS` | `60000` | Batas atas jeda. |
| `MAX_RETRIES` | `10` | Melebihi ini, item dibuang. |
| `REQUEST_TIMEOUT_SECONDS` | `15` | Tenggat setiap permintaan HTTP. |
| `MAX_QUEUE_AGE_SECONDS` | `300` | Umur maksimum item sebelum dibuang. |
| `RUST_LOG` | *(kosong)* | Contoh: `RUST_LOG=info`. |

---

## Membangun dan menjalankan

### Prasyarat

Toolchain yang terpasang dan terverifikasi di mesin ini:

| Komponen | Versi | Catatan |
|---|---|---|
| Rust | 1.97.1, host `x86_64-pc-windows-gnu` | Dipasang lewat <https://rustup.rs> |
| MinGW-w64 gcc | 16.1.0 (WinLibs UCRT) | **Wajib** — `ring` (lewat `rustls`) mengompilasi kode C, dan toolchain GNU tidak membawa compiler C sendiri. `winget install BrechtSanders.WinLibs.POSIX.UCRT` |

Host MSVC juga bisa dipakai, tetapi menuntut Visual Studio Build Tools plus
Windows SDK yang jauh lebih besar. Setelah memasang gcc, buka terminal baru agar
PATH termuat ulang.

### Perintah

```bash
cd apps/kiosk-agent-rust

cargo build --release                    # mode berkas saja
cargo build --release --features camera  # dengan dukungan kamera

cargo test                               # 10 uji unit antrean
cargo clippy --all-targets               # pemeriksaan lint

RUST_LOG=info cargo run
```

Di Windows, dukungan kamera memakai backend Media Foundation lewat
`nokhwa-bindings-windows`, yang aktif melalui fitur `input-native`.

---

## Riwayat perbaikan

Sepuluh masalah diperbaiki pada 3 Agustus 2026. Delapan pertama ditemukan lewat
pembacaan kode, dua terakhir baru terungkap setelah kompiler dan test dijalankan.

| # | Lokasi | Masalah | Bukti |
|---|---|---|---|
| 1 | `Cargo.toml` | `nokhwa = "0.5"` menarik `mozjpeg 0.8.24` yang sudah **yanked**, sehingga resolusi dependensi gagal total. Versi itu juga salah: kode memanggil API `CameraIndex`/`RequestedFormat` yang baru ada di 0.10. Kini `nokhwa = "0.10"` dengan fitur `input-native`. | `cargo check` gagal di tahap resolusi |
| 2 | `src/config.rs` | `if let Ok(index) = env::var(..).ok().and_then(..)` mencocokkan pola `Result` terhadap `Option<u32>`. | `error[E0308]: mismatched types` |
| 3 | `src/main.rs` | `&frame_source` bertipe `&Box<dyn FrameSource>` tidak meluruh otomatis menjadi `&dyn FrameSource`. Kini `frame_source.as_ref()`. | `error[E0277]: Box<dyn FrameSource>: FrameSource` |
| 4 | `src/capture.rs` | `nokhwa::utils::MJPEGFormat` tidak ada di 0.10; penggantinya `pixel_format::RgbFormat`. | `error[E0432]: unresolved import` |
| 5 | `src/capture.rs` | `nokhwa::Camera` bukan `Send`, sehingga mustahil dipakai di trait `Send + Sync` atau melintasi `await`. Kamera dipindah ke thread khusus. | `error[E0277]: cannot be sent between threads safely` |
| 6 | `src/capture.rs` | `buf` dipindahkan ke `RgbImage::from_raw(..., buf)` lalu `buf.len()` dipakai di closure galat. Hilang bersama penulisan ulang `grab_jpeg`. | pemakaian setelah pindah |
| 7 | `src/main.rs` | Cabang Unix memakai `term.ok()` di `tokio::select!`, padahal `Option<Signal>` bukan future → gagal build di Linux/macOS. | `error[E0277]: Option<Signal> is not a future`, dibuktikan lewat `cargo check --target x86_64-unknown-linux-gnu` pada crate terisolasi |
| 8 | `src/queue.rs` | `1u64.saturating_pow(retry_count)` selalu 1, jadi backoff **konstan** bukan eksponensial. Kini `2u64`. | `test_backoff_exponential` gagal |
| 9 | `src/queue.rs` | **`fastrand::u64(0..0)` panik** saat jeda hasil hitungan bernilai 0 — mis. `RETRY_BASE_BACKOFF_MS=0`. Agen ikut mati. Kini jitter dilewati bila rentangnya kosong. | 3 test panik: `empty range: Included(0)..Excluded(0)` |
| 10 | `src/queue.rs` (test) | `test_backoff_exponential` menuntut `b1 <= 200`, yang hanya benar bila backoff konstan — bertentangan dengan `b2 >= 400` di baris berikutnya. Ekspektasi diselaraskan ke rumus sebenarnya. | test gagal setelah #8 diperbaiki |

Perbaikan perilaku lain yang menyertainya:

- `queue_depth` pada heartbeat tidak lagi ditulis mati `0`, sehingga agen yang
  menumpuk antrean tidak lagi terlihat sehat dari sisi backend.
- Satu siklus kini mengirim sampai `MAX_SENDS_PER_TICK` (8) item, bukan satu.
  Dengan satu item per siklus, antrean mustahil menyusut karena setiap siklus
  juga menambah satu frame baru.
- Frame yang ditolak penyaring liveness kini dicatat lengkap dengan skor,
  ambang, dan kecerahannya — sebelumnya dibuang diam-diam sehingga keluhan
  "tidak ada yang terkirim" mustahil didiagnosis.
- `CAMERA_WIDTH` dan `CAMERA_HEIGHT` benar-benar dipakai (lihat
  `RequestedFormatType::Closest`), tidak lagi diterima lalu diabaikan.

### Hasil verifikasi

```
cargo check                                  OK
cargo check --features camera                OK
cargo clippy --all-targets                   OK, tanpa peringatan
cargo clippy --all-targets --features camera OK, tanpa peringatan
cargo test                                   10 passed; 0 failed
cargo build --release --features camera      OK, biner 21,8 MB
```

Uji asap terhadap backend yang sengaja dimatikan menunjukkan siklus
tangkap → antre → kirim → hitung retry → backoff berjalan tanpa panik.

---

## Hubungan dengan kiosk web

Kiosk yang dipakai sekarang adalah `apps/kiosk-ui/` — halaman statis yang dilayani
langsung oleh API. Kamera diakses di browser, bukan lewat agen ini:

| Fungsi di `apps/kiosk-ui/src/main.js` | Peran |
|---|---|
| `startCamera` | Meminta izin dan membuka aliran video lewat `getUserMedia`, dengan rangkaian percobaan dan penanganan kamera belakang. |
| `enumerateCameras` | Mendaftar perangkat `videoinput` yang tersedia. |
| `cameraStartupAttempts` | Menyusun urutan percobaan: kamera tersimpan, kamera depan, lalu bebas. |
| `captureAttendanceFrames` | Mengambil tiga frame untuk dikirim ke `/attendance/preview`. |

Perbedaan penting: agen Rust mengirim ke `/recognize` yang mencatat absensi
langsung, sedangkan kiosk web memakai alur dua langkah `/attendance/preview` →
`/attendance/confirm` yang menampilkan konfirmasi wajah lebih dulu kepada pengguna.
