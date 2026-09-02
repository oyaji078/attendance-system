/* Rekap Per Mata Pelajaran — the detail matrix.
 *
 * One subject + one class + one period, students down, meetings across. P1..Pn
 * is driven by the schedule's own meeting count, so 12, 16 or 20 all render the
 * same way. No pagination: the table scrolls with a sticky header and sticky
 * identity columns. */

import { api, download, query } from "../api.js";
import {
  attendanceCode,
  emptyState,
  esc,
  fmtDate,
  fmtDateShort,
  fmtPercent,
  icon,
  legend,
  percentCell,
  selectField,
  skeletonTable,
} from "../ui.js";

const state = { subjectId: "", classId: "", period: "", scheduleId: "" };

function periodKey(schedule) {
  return `${schedule.academic_year}|${schedule.semester}`;
}

function periodLabel(schedule) {
  return `${schedule.academic_year} ${schedule.semester.charAt(0).toUpperCase()}${schedule.semester.slice(1)}`;
}

export default {
  title: "Rekap Per Mata Pelajaran",

  async render(app) {
    app.paint(skeletonTable(8));

    const response = await api.get("/academic/schedules");
    const schedules = response.items ?? [];

    // A jadwal already is subject + class + period, so the three pickers simply
    // narrow the schedule list down to one.
    if (app.params.scheduleId) {
      const preset = schedules.find((item) => item.schedule_id === app.params.scheduleId);
      if (preset) {
        state.subjectId = preset.subject_id;
        state.classId = preset.class_id;
        state.period = periodKey(preset);
        state.scheduleId = preset.schedule_id;
      }
      app.params.scheduleId = null;
    }

    const subjects = [...new Map(schedules.map((item) => [item.subject_id, item])).values()];
    if (!state.subjectId && subjects.length) state.subjectId = subjects[0].subject_id;

    const forSubject = schedules.filter((item) => item.subject_id === state.subjectId);
    const classes = [...new Map(forSubject.map((item) => [item.class_id, item])).values()];
    if (!classes.some((item) => item.class_id === state.classId)) state.classId = classes[0]?.class_id ?? "";

    const forClass = forSubject.filter((item) => item.class_id === state.classId);
    const periods = [...new Map(forClass.map((item) => [periodKey(item), item])).values()];
    if (!periods.some((item) => periodKey(item) === state.period)) state.period = periods[0] ? periodKey(periods[0]) : "";

    const schedule = forClass.find((item) => periodKey(item) === state.period) ?? null;
    state.scheduleId = schedule?.schedule_id ?? "";

    const controls = `<div class="aps-filters">
      ${selectField("Mata Pelajaran", "subjectId", subjects.map((item) => ({ value: item.subject_id, label: item.subject_name })), state.subjectId, { stack: true, allLabel: null })}
      ${selectField("Kelas", "classId", classes.map((item) => ({ value: item.class_id, label: `${item.class_code}` })), state.classId, { stack: true, allLabel: null })}
      ${selectField("Periode", "period", periods.map((item) => ({ value: periodKey(item), label: periodLabel(item) })), state.period, { stack: true, allLabel: null })}
      <div class="aps-toolbar-spacer"></div>
      ${
        schedule
          ? `<div style="display:flex;gap:var(--s-2);align-self:end">
              <button class="aps-btn aps-btn--ghost aps-btn--sm" data-act="pdf" type="button">${icon("download")} PDF</button>
              <button class="aps-btn aps-btn--ghost aps-btn--sm" data-act="excel" type="button">${icon("download")} Excel</button>
              <button class="aps-btn aps-btn--ghost aps-btn--sm" data-act="print" type="button">${icon("print")} Print</button>
            </div>`
          : ""
      }
    </div>`;

    if (!schedules.length) {
      app.paint(
        controls +
          emptyState({
            title: "Belum ada jadwal",
            description: "Rekap dihitung dari jadwal dan pertemuan. Tambahkan jadwal terlebih dahulu.",
          }),
      );
      return;
    }
    if (!schedule) {
      app.paint(controls + emptyState({ title: "Pilih kombinasi mata pelajaran, kelas, dan periode" }));
      return;
    }

    const recap = await api.get(`/academic/schedules/${schedule.schedule_id}/recap`);

    if (!recap.rows.length) {
      app.paint(
        controls +
          emptyState({
            title: "Belum ada siswa di kelas ini",
            description: "Tempatkan siswa ke kelas melalui menu Siswa → Kelola Kelas.",
          }),
      );
      return;
    }

    const head = `<tr>
      <th class="aps-sticky-1 aps-num">No</th>
      <th class="aps-sticky-2">NISN</th>
      <th class="aps-sticky-3">Nama</th>
      ${recap.columns
        .map(
          (column) => `<th class="aps-meeting-head" title="Pertemuan ${column.meeting_number}${
            column.meeting_date ? ` — ${fmtDate(column.meeting_date)}` : " — belum dijadwalkan"
          }${column.status === "held" ? "" : " (belum dilaksanakan)"}">
            <strong>P${column.meeting_number}</strong>
            <span>${column.meeting_date ? esc(fmtDateShort(column.meeting_date)) : "—"}</span>
          </th>`,
        )
        .join("")}
      <th class="aps-center">H</th><th class="aps-center">I</th>
      <th class="aps-center">S</th><th class="aps-center">A</th>
      <th>Kehadiran</th>
    </tr>`;

    const body = recap.rows
      .map(
        (row) => `<tr>
          <td class="aps-sticky-1 aps-num">${row.no}</td>
          <td class="aps-sticky-2">${esc(row.student_id)}</td>
          <td class="aps-sticky-3 aps-strong">${esc(row.full_name)}</td>
          ${row.cells
            .map((cell, index) => {
              const pending = recap.columns[index]?.status !== "held";
              return `<td class="aps-center${pending ? " aps-cell-pending" : ""}">${pending && !cell ? "" : attendanceCode(cell)}</td>`;
            })
            .join("")}
          <td class="aps-center">${row.hadir}</td>
          <td class="aps-center">${row.izin}</td>
          <td class="aps-center">${row.sakit}</td>
          <td class="aps-center">${row.alpha}</td>
          <td>${percentCell(row.held_meetings ? row.attendance_percent : null)}</td>
        </tr>`,
      )
      .join("");

    const notice =
      recap.total_meetings === 0
        ? `<div class="aps-alert aps-alert--info" role="status">
            <span>Jadwal ini belum punya pertemuan, jadi belum ada kehadiran yang bisa dihitung.
            Pertemuan dibuat otomatis saat absensi pertama, atau buat sekarang.</span>
            <button class="aps-btn aps-btn--sm" data-act="make-meetings" type="button">Buat Pertemuan</button>
          </div>`
        : recap.held_meetings === 0
          ? `<div class="aps-alert aps-alert--info" role="status">
              <span>Belum ada pertemuan yang terlaksana. Persentase muncul setelah absensi pertama
              tercatat — lewat kamera di Mode Absensi, atau koreksi manual di menu Absensi.</span>
            </div>`
          : "";

    app.paint(`
      ${controls}
      ${notice}
      <section class="aps-card">
        <div class="aps-card-body" style="padding:var(--s-4) var(--s-5)">
          <dl class="aps-facts">
            <div><dt>Mata Pelajaran</dt><dd class="aps-strong">${esc(recap.schedule.subject_name ?? "-")}</dd></div>
            <div><dt>Kelas</dt><dd>${esc(recap.schedule.class_code ?? "-")} — ${esc(recap.schedule.class_name ?? "")}</dd></div>
            <div><dt>Guru</dt><dd>${esc(recap.schedule.lecturer_name ?? "—")}</dd></div>
            <div><dt>Periode</dt><dd>${esc(periodLabel(recap.schedule))}</dd></div>
            <div><dt>Pertemuan Terlaksana</dt><dd>${recap.held_meetings} dari ${recap.total_meetings}</dd></div>
            <div><dt>Rata-rata Kehadiran</dt><dd>${esc(fmtPercent(recap.average_percent))}</dd></div>
          </dl>
        </div>
      </section>
      <div class="aps-tablewrap aps-tablewrap--tall">
        <table class="aps-table"><thead>${head}</thead><tbody>${body}</tbody></table>
      </div>
      ${legend()}
      <p class="aps-hint" style="margin:0">
        Persentase kehadiran = Hadir ÷ pertemuan yang sudah dilaksanakan × 100.
        Kolom bergaris adalah pertemuan yang belum dilaksanakan dan tidak dihitung sebagai Alpa.
      </p>`);
  },

  mount(app) {
    const host = app.content();
    host.querySelectorAll("[data-filter]").forEach((select) =>
      select.addEventListener("change", () => {
        state[select.dataset.filter] = select.value;
        app.reload();
      }),
    );
    host.querySelector("[data-act=pdf]")?.addEventListener("click", () =>
      download(`/academic/schedules/${state.scheduleId}/recap/export${query({ format: "pdf" })}`),
    );
    host.querySelector("[data-act=excel]")?.addEventListener("click", () =>
      download(`/academic/schedules/${state.scheduleId}/recap/export${query({ format: "excel" })}`),
    );
    host.querySelector("[data-act=print]")?.addEventListener("click", () => window.print());
    host.querySelector("[data-act=make-meetings]")?.addEventListener("click", async () => {
      try {
        await api.post(`/academic/schedules/${state.scheduleId}/meetings/generate`, {});
        app.notify("Pertemuan dibuat.");
        app.reload();
      } catch (error) {
        app.notify(error?.message ?? "Pertemuan gagal dibuat.", "danger");
      }
    });
  },
};
