/* Detail kelas — Overview, Siswa, Mata Pelajaran, Jadwal.
 * "Mata Pelajaran" and "Jadwal" here are the same records: a schedule is what
 * binds a subject to this class, so both tabs read the class's schedules. */

import { api, query } from "../api.js";
import {
  badge,
  emptyState,
  esc,
  fmtDate,
  fmtRange,
  icon,
  DAY_LABELS,
  skeletonTable,
  statusBadge,
} from "../ui.js";

const state = { tab: "overview" };

export default {
  title: (app) => app.params.name ?? "Detail Kelas",

  breadcrumb: () => `<button data-crumb="classes" type="button">Kelas</button><span>/</span><span>Detail</span>`,

  async render(app) {
    app.paint(skeletonTable(6));
    const classId = app.params.classId;
    const [detail, scheduleResponse] = await Promise.all([
      api.get(`/console/classes/${classId}`),
      api.get(`/academic/schedules${query({ class_id: classId })}`),
    ]);
    app.params.name = `${detail.class_code} — ${detail.class_name}`;
    const schedules = scheduleResponse.items ?? [];

    const tabs = `<div class="aps-tabs" role="tablist">
      ${[
        ["overview", "Overview"],
        ["students", `Siswa (${detail.student_count})`],
        ["subjects", `Mata Pelajaran (${schedules.length})`],
        ["schedule", "Jadwal"],
      ]
        .map(
          ([key, label]) =>
            `<button class="aps-tab" role="tab" data-tab="${key}" aria-selected="${state.tab === key}" type="button">${esc(label)}</button>`,
        )
        .join("")}
    </div>`;

    let body = "";
    if (state.tab === "overview") {
      body = `<section class="aps-card"><div class="aps-card-body">
        <dl class="aps-facts">
          <div><dt>Kode Kelas</dt><dd class="aps-strong">${esc(detail.class_code)}</dd></div>
          <div><dt>Nama Kelas</dt><dd>${esc(detail.class_name)}</dd></div>
          <div><dt>Wali Kelas</dt><dd>${esc(detail.lecturer_name ?? "—")}</dd></div>
          <div><dt>Status</dt><dd>${statusBadge(detail.is_active)}</dd></div>
          <div><dt>Jumlah Siswa</dt><dd>${detail.student_count}</dd></div>
          <div><dt>Mata Pelajaran</dt><dd>${detail.schedule_count}</dd></div>
          <div><dt>Keterangan</dt><dd>${esc(detail.description ?? "—")}</dd></div>
        </dl>
      </div></section>`;
    } else if (state.tab === "students") {
      body = detail.students.length
        ? `<div class="aps-tablewrap"><table class="aps-table">
            <thead><tr><th class="aps-num">No</th><th>NISN</th><th>Nama</th><th>Status</th><th>Data Wajah</th><th>Sejak</th></tr></thead>
            <tbody>${detail.students
              .map(
                (row) => `<tr>
                  <td class="aps-num">${row.no}</td>
                  <td>${esc(row.student_id)}</td>
                  <td><button data-student="${esc(row.person_id)}" type="button"
                       style="border:0;background:none;padding:0;font:inherit;font-weight:600;color:var(--c-brand);cursor:pointer">${esc(row.full_name)}</button></td>
                  <td>${statusBadge(row.is_active)}</td>
                  <td>${row.has_face_profile ? badge("Terdaftar", "success") : badge("Belum", "neutral")}</td>
                  <td>${row.start_date ? esc(fmtDate(row.start_date)) : "—"}</td>
                </tr>`,
              )
              .join("")}</tbody>
          </table></div>`
        : emptyState({
            title: "Belum ada siswa di kelas ini",
            description: "Tempatkan siswa melalui menu Siswa → Kelola Kelas.",
          });
    } else if (state.tab === "subjects") {
      body = schedules.length
        ? `<div class="aps-tablewrap"><table class="aps-table">
            <thead><tr><th>Mata Pelajaran</th><th>Guru</th><th>Periode</th><th class="aps-num">Pertemuan</th><th></th></tr></thead>
            <tbody>${schedules
              .map(
                (item) => `<tr>
                  <td><span class="aps-strong">${esc(item.subject_name ?? "-")}</span><span class="aps-sub">${esc(item.subject_code ?? "")}</span></td>
                  <td>${esc(item.lecturer_name ?? "—")}</td>
                  <td>${esc(item.academic_year)} ${esc(item.semester)}</td>
                  <td class="aps-num">${item.held_meeting_count ?? 0}/${item.total_meetings}</td>
                  <td class="aps-actions"><button class="aps-btn aps-btn--ghost aps-btn--sm" data-recap="${esc(item.schedule_id)}" type="button">Rekap</button></td>
                </tr>`,
              )
              .join("")}</tbody>
          </table></div>`
        : emptyState({
            title: "Belum ada mata pelajaran",
            description: "Tambahkan jadwal untuk menghubungkan mata pelajaran ke kelas ini.",
            action: `<button class="aps-btn" data-act="go-schedule" type="button">${icon("plus")} Tambah Jadwal</button>`,
          });
    } else {
      body = schedules.length
        ? `<div class="aps-tablewrap"><table class="aps-table">
            <thead><tr><th>Hari</th><th>Jam</th><th>Mata Pelajaran</th><th>Guru</th><th>Ruang</th></tr></thead>
            <tbody>${schedules
              .map(
                (item) => `<tr>
                  <td>${esc(DAY_LABELS[item.day_of_week] ?? "—")}</td>
                  <td>${esc(fmtRange(item.start_time, item.end_time))}</td>
                  <td>${esc(item.subject_name ?? "-")}</td>
                  <td>${esc(item.lecturer_name ?? "—")}</td>
                  <td>${esc(item.room ?? "—")}</td>
                </tr>`,
              )
              .join("")}</tbody>
          </table></div>`
        : emptyState({
            title: "Belum ada jadwal",
            description: "Tambahkan jadwal untuk kelas ini.",
            action: `<button class="aps-btn" data-act="go-schedule" type="button">${icon("plus")} Tambah Jadwal</button>`,
          });
    }

    app.paint(`
      <div class="aps-toolbar">
        <button class="aps-btn aps-btn--ghost aps-btn--sm" data-act="back" type="button">${icon("back")} Kembali</button>
        <div class="aps-toolbar-spacer"></div>
        <button class="aps-btn aps-btn--ghost aps-btn--sm" data-act="class-recap" type="button">${icon("recap")} Rekap Kelas</button>
      </div>
      ${tabs}${body}`);
  },

  mount(app) {
    const host = app.content();
    host.querySelector("[data-act=back]")?.addEventListener("click", () => app.back());
    host.querySelector("[data-act=class-recap]")?.addEventListener("click", () =>
      app.navigate("recap-class", { classId: app.params.classId }),
    );
    host.querySelector("[data-act=go-schedule]")?.addEventListener("click", () =>
      app.navigate("schedule", { classId: app.params.classId }),
    );
    host.querySelectorAll("[data-tab]").forEach((button) =>
      button.addEventListener("click", () => {
        state.tab = button.dataset.tab;
        app.reload();
      }),
    );
    host.querySelectorAll("[data-student]").forEach((button) =>
      button.addEventListener("click", () => app.navigate("student-detail", { personId: button.dataset.student })),
    );
    host.querySelectorAll("[data-recap]").forEach((button) =>
      button.addEventListener("click", () => app.navigate("recap-subject", { scheduleId: button.dataset.recap })),
    );
    document.querySelectorAll("[data-crumb]").forEach((button) =>
      button.addEventListener("click", () => app.navigate(button.dataset.crumb)),
    );
  },
};
