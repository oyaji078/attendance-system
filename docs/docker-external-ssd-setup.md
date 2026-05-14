# Setup Docker di SSD Eksternal Windows

Dokumen ini menjelaskan cara menyiapkan project agar model tetap berada di folder project, sementara storage Docker Desktop dapat diarahkan ke SSD eksternal `E:`.

## A. Konsep penyimpanan

Docker image, container, named volume, dan build cache adalah storage global Docker. Storage ini berbeda dari folder model project.

Untuk project ini, model tetap berada di folder local project:

```text
./models
```

Container membaca model lewat bind mount ke path container:

```text
./models:/app/models
```

Jangan memasukkan model besar ke Docker image. Model yang di-copy ke image akan membuat image sangat besar, memperlambat build, dan memenuhi storage Docker global.

Docker global storage boleh dipindahkan ke SSD eksternal lewat Docker Desktop. Folder `./models` tetap dikelola sebagai file project dan tidak dipindahkan otomatis ke Docker global storage.

## B. Rekomendasi format SSD

Untuk Windows dan Docker Desktop, gunakan NTFS.

Hindari exFAT untuk workload Docker yang intensif karena permission, metadata, dan reliability dapat bermasalah.

Jika SSD masih berisi data, lakukan backup terlebih dahulu sebelum melakukan format manual. Script di repository ini tidak memformat drive dan tidak menghapus data.

## C. Struktur folder SSD E:

Struktur yang direkomendasikan:

```text
E:\DockerData
E:\DockerData\docker
E:\DockerData\volumes
E:\DockerData\cache
E:\DockerData\logs
```

Buat folder tersebut dengan:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-docker-external-ssd.ps1
```

## D. Memindahkan Docker Desktop data ke E:

### Opsi 1 - Lewat Docker Desktop UI

1. Pastikan SSD eksternal terpasang sebagai drive `E:`.
2. Buka Docker Desktop.
3. Buka Settings.
4. Buka Resources.
5. Buka Advanced.
6. Cari `Disk image location`.
7. Ubah lokasi ke drive E:, misalnya:

```text
E:\DockerData\docker
```

8. Pilih Apply & Restart.
9. Setelah Docker Desktop aktif kembali, verifikasi dengan:

```powershell
docker info
docker system df
```

### Opsi 2 - Jika memakai WSL2 backend dan UI tidak cukup

Gunakan opsi ini hanya jika Docker Desktop UI tidak berhasil atau versi Docker Desktop yang digunakan tidak menyediakan pengaturan yang cukup.

Langkah aman manual:

1. Tutup container dan Docker Desktop dengan normal.
2. Pastikan SSD `E:` terpasang dan folder `E:\DockerData` sudah ada.
3. Buat backup WSL Docker sebelum perubahan:

```powershell
wsl --shutdown
wsl --export docker-desktop-data E:\DockerData\logs\docker-desktop-data-backup.tar
```

4. Pastikan file backup berhasil dibuat dan ukurannya masuk akal.
5. Ikuti dokumentasi resmi Docker Desktop untuk migrasi WSL data location sesuai versi Docker Desktop yang digunakan.

Catatan penting: beberapa prosedur WSL manual memerlukan unregister/import distro WSL. Langkah tersebut berisiko menghilangkan data jika backup tidak valid. Jangan menjalankannya tanpa backup yang sudah diverifikasi dan pemahaman penuh terhadap dampaknya.

## E. Menjalankan project

Dari root repository:

```powershell
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml logs -f
docker system df
docker info
```

Jika menjalankan compose dari workflow yang membaca `.env`, path Windows dapat ditulis sebagai:

```env
DOCKER_EXTERNAL_ROOT=E:\DockerData
DOCKER_EXTERNAL_VOLUME_DIR=E:\DockerData\volumes
DOCKER_EXTERNAL_CACHE_DIR=E:\DockerData\cache
```

Jika Docker Compose bermasalah dengan backslash, gunakan format slash:

```env
DOCKER_EXTERNAL_ROOT=E:/DockerData
DOCKER_EXTERNAL_VOLUME_DIR=E:/DockerData/volumes
DOCKER_EXTERNAL_CACHE_DIR=E:/DockerData/cache
```

## F. Verifikasi

Jalankan:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify-docker-storage.ps1
```

Yang perlu dipastikan:

- Container dapat membaca model dari `/app/models`.
- `docker/api.Dockerfile` tidak menyalin folder `models` ke image.
- Docker Desktop `Disk image location` mengarah ke `E:\DockerData\docker`.
- SSD eksternal sudah terpasang sebelum Docker Desktop dijalankan.
- `docker compose -f docker/docker-compose.yml config` valid.

Verifikasi manual mount model:

```powershell
docker compose -f docker/docker-compose.yml exec api ls -la /app/models
```

## G. Troubleshooting

Docker gagal start karena SSD belum terpasang:
Pastikan drive `E:` tersedia sebelum membuka Docker Desktop. Jika Docker Desktop sudah error, tutup Docker Desktop, pasang SSD, lalu buka ulang.

Path `E:` tidak ditemukan:
Pastikan Windows masih memberi drive letter `E:` untuk SSD. Jika berubah, atur ulang lewat Disk Management.

Permission error:
Pastikan user Windows punya akses penuh ke `E:\DockerData`. Jalankan Docker Desktop sebagai user yang sama dengan user project.

Bind mount `models` tidak terbaca:
Pastikan folder `models` ada di root repository. Compose project ini memasang `../models` ke `/app/models` karena file compose berada di folder `docker`.

Docker Compose gagal membaca path Windows:
Gunakan format slash seperti `E:/DockerData/volumes` untuk nilai env Windows.

SSD dicabut saat container berjalan:
Hentikan container dan Docker Desktop sebelum melepas SSD. Mencabut SSD saat Docker aktif dapat menyebabkan error atau korupsi data.
