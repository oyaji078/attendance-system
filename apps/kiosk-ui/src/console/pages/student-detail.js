/* Detail siswa — identity, then three tabs: Ringkasan, Enrollment, Absensi. */

import { api, photoUrl } from "../api.js";
import {
  attendanceCode,
  badge,
  initials,
  emptyState,
  esc,
  fmtDate,
  fmtDateTime,
  icon,
  percentCell,
  skeletonTable,
  statusBadge,
} from "../ui.js";

const state = { tab: "summary" };

export default {
  title: (app) => app.params.name ?? "Detail Siswa",

  breadcrumb: () =>
    `<button data-crumb="students" type="button">Siswa</button><span>/</span><span>Detail</span>`,

  async render(app) {
    app.paint(skeletonTable(6));
    const data = await api.get(`/console/students/${app.params.personId}`);
    app.params.name = data.full_name;
    state.data = data;

    // The photo comes from the most recent active face sample; a student who
    // has not been enrolled yet has none, so the <img> falls back to initials.
    const header = `<section class="aps-card">
      <div class="aps-card-body aps-identity">
        <div class="aps-photo">
          ${
            data.has_face_profile
              ? `<img src="${photoUrl(data.person_id)}" alt="Foto ${esc(data.full_name)}"
                   data-role="photo" loading="lazy" />`
              : ""
          }
          <span class="aps-photo-fallback">${esc(initials(data.full_name))}</span>
        </div>
        <dl class="aps-facts" style="flex:1 1 auto">
          <div><dt>Nama</dt><dd class="aps-strong">${esc(data.full_name)}</dd></div>
          <div><dt>NISN</dt><dd>${esc(data.student_id)}</dd></div>
          <div><dt>Kelas</dt><dd>${data.class_code ? `${esc(data.class_code)} — ${esc(data.class_name ?? "")}` : "Belum ditempatkan"}</dd></div>
          <div><dt>Status</dt><dd>${statusBadge(data.is_active)}</dd></div>
          <div><dt>Data Wajah</dt><dd>${data.has_face_profile ? badge("Terdaftar", "success") : badge("Belum terdaftar", "warning")}</dd></div>
          <div><dt>Terakhir Dikenali</dt><dd>${data.last_seen_at ? esc(fmtDateTime(data.last_seen_at)) : "—"}</dd></div>
        </dl>
      </div>
    </section>`;

    const tabs = `<div class="aps-tabs" role="tablist">
      ${[
        ["summary", "Ringkasan"],
        ["enrollment", "Enrollment"],
        ["attendance", "Absensi"],
      ]
        .map(
          ([key, label]) =>
            `<button class="aps-tab" role="tab" data-tab="${key}" aria-selected="${state.tab === key}" type="button">${label}</button>`,
        )
        .join("")}
    </div>`;

    let body = "";
    if (state.tab === "summary") {
      body = `<section class="aps-card"><div class="aps-card-body">
        <dl class="aps-facts">
          <div><dt>Alamat</dt><dd>${esc(data.address || "—")}</dd></div>
          <div><dt>Email</dt><dd>${esc(data.email || "—")}</dd></div>
          <div><dt>Mata pelajaran diikuti</dt><dd>${data.subjects.length}</dd></div>
        </dl>
      </div></section>`;
    } else if (state.tab === "enrollment") {
      body = data.enrollments.length
        ? `<div class="aps-tablewrap"><table class="aps-table">
            <thead><tr><th>Kelas</th><th>Status</th><th>Mulai</th><th>Selesai</th><th>Catatan</th></tr></thead>
            <tbody>${data.enrollments
              .map(
                (item) => `<tr>
                  <td><span class="aps-strong">${esc(item.class_code ?? "-")}</span><span class="aps-sub">${esc(item.class_name ?? "")}</span></td>
                  <td>${item.status === "active" ? badge("Aktif", "success") : badge("Selesai", "neutral")}</td>
                  <td>${item.start_date ? esc(fmtDate(item.start_date)) : "—"}</td>
                  <td>${item.end_date ? esc(fmtDate(item.end_date)) : "—"}</td>
                  <td>${esc(item.note ?? "—")}</td>
                </tr>`,
              )
              .join("")}</tbody>
          </table></div>`
        : emptyState({
            title: "Belum ada riwayat kelas",
            description: "Tempatkan siswa ke kelas melalui menu Siswa → Kelola Kelas.",
          });
    } else {
      body = data.subjects.length
        ? `<div class="aps-tablewrap"><table class="aps-table">
            <thead><tr>
              <th>Mata Pelajaran</th>
              <th class="aps-center">H</th><th class="aps-center">I</th>
              <th class="aps-center">S</th><th class="aps-center">A</th>
              <th class="aps-num">Pertemuan</th><th>Kehadiran</th>
            </tr></thead>
            <tbody>${data.subjects
              .map(
                (item) => `<tr>
                  <td><span class="aps-strong">${esc(item.subject_name)}</span><span class="aps-sub">${esc(item.subject_code ?? "")}</span></td>
                  <td class="aps-center">${item.hadir}</td>
                  <td class="aps-center">${item.izin}</td>
                  <td class="aps-center">${item.sakit}</td>
                  <td class="aps-center">${item.alpha}</td>
                  <td class="aps-num">${item.held_meetings}</td>
                  <td>${item.held_meetings ? percentCell(item.attendance_percent) : attendanceCode(null)}</td>
                </tr>`,
              )
              .join("")}</tbody>
          </table></div>`
        : emptyState({
            title: "Belum ada data kehadiran",
            description: "Kehadiran muncul setelah kelas siswa ini memiliki jadwal dan pertemuan yang terlaksana.",
          });
    }

    app.paint(`
      <div class="aps-toolbar">
        <button class="aps-btn aps-btn--ghost aps-btn--sm" data-act="back" type="button">${icon("back")} Kembali</button>
      </div>
      ${header}${tabs}${body}`);
  },

  mount(app) {
    const host = app.content();
    host.querySelector("[data-act=back]")?.addEventListener("click", () => app.back());
    host.querySelectorAll("[data-tab]").forEach((button) =>
      button.addEventListener("click", () => {
        state.tab = button.dataset.tab;
        app.reload();
      }),
    );
    document.querySelectorAll("[data-crumb]").forEach((button) =>
      button.addEventListener("click", () => app.navigate(button.dataset.crumb)),
    );
  },
};
