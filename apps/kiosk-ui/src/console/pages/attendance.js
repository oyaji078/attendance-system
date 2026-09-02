/* Absensi — the transaction log, plus the correction path.
 *
 * Face recognition is the source; this page shows what was recorded and lets
 * staff correct a row when the camera got it wrong or a student was absent from
 * the kiosk entirely. Corrections are explicit and land in the same ledger, so
 * the recap always reflects them. */

import { api, query } from "../api.js";
import {
  ATTENDANCE_LABELS,
  accuracyCell,
  attendanceCode,
  badge,
  emptyState,
  esc,
  fmtDate,
  fmtDateTime,
  fmtRange,
  icon,
  kebab,
  legend,
  selectField,
  showDrawer,
  showMenu,
  skeletonTable,
} from "../ui.js";

const state = { date: "", classId: "", subjectId: "", status: "", source: "", rows: [] };

async function sheetDrawer(app, schedule) {
  /* Bulk correction for a whole meeting: pick the meeting, then adjust. */
  const response = await api.get(`/academic/schedules/${schedule.schedule_id}/meetings`);
  const meetings = response.items ?? [];
  if (!meetings.length) {
    showDrawer({
      title: "Belum ada pertemuan",
      body: `<p style="color:var(--c-muted);margin:0">Jadwal ini belum memiliki pertemuan. Buat pertemuan terlebih dahulu agar absensi dapat dicatat.</p>`,
      submitLabel: "Buat Pertemuan",
      async onSubmit() {
        await api.post(`/academic/schedules/${schedule.schedule_id}/meetings/generate`, {});
        app.notify("Pertemuan dibuat.");
        app.reload();
      },
    });
    return;
  }

  showDrawer({
    title: "Koreksi Absensi",
    description: `${schedule.class_code} · ${schedule.subject_name}`,
    submitLabel: "Buka",
    body: `<label>Pertemuan
      <select name="meeting_id">
        ${meetings
          .map(
            (item) =>
              `<option value="${esc(item.meeting_id)}">Pertemuan ${item.meeting_number}${item.meeting_date ? ` · ${fmtDate(item.meeting_date)}` : ""}${item.status === "held" ? " ✓" : ""}</option>`,
          )
          .join("")}
      </select>
    </label>`,
    async onSubmit(values) {
      await openMeetingSheet(app, values.meeting_id);
    },
  });
}

async function openMeetingSheet(app, meetingId) {
  const sheet = await api.get(`/academic/meetings/${meetingId}/attendance`);
  const rows = sheet.students
    .map(
      (student) => `<tr>
        <td class="aps-num">${student.no}</td>
        <td><span class="aps-strong">${esc(student.full_name)}</span><span class="aps-sub">${esc(student.student_id)}</span></td>
        <td>
          <select name="status-${esc(student.person_id)}" style="min-width:104px">
            <option value=""${student.status ? "" : " selected"}>—</option>
            ${Object.entries(ATTENDANCE_LABELS)
              .map(
                ([code, label]) =>
                  `<option value="${code}"${student.status === code ? " selected" : ""}>${code} · ${label}</option>`,
              )
              .join("")}
          </select>
        </td>
      </tr>`,
    )
    .join("");

  showDrawer({
    title: `Pertemuan ${sheet.meeting.meeting_number}`,
    description: `${sheet.schedule.class_code} · ${sheet.schedule.subject_name} · ${sheet.student_count} siswa`,
    submitLabel: "Simpan Koreksi",
    wide: true,
    body: `
      <div class="aps-toolbar">
        <button class="aps-btn aps-btn--ghost aps-btn--sm" data-bulk="H" type="button">Semua Hadir</button>
        <button class="aps-btn aps-btn--ghost aps-btn--sm" data-bulk="" type="button">Kosongkan</button>
      </div>
      <div class="aps-tablewrap" style="max-height:52vh">
        <table class="aps-table">
          <thead><tr><th class="aps-num">No</th><th>Siswa</th><th>Status</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      ${legend()}`,
    async onSubmit(values) {
      const entries = Object.entries(values)
        .filter(([key, value]) => key.startsWith("status-") && value)
        .map(([key, value]) => ({ person_id: key.replace("status-", ""), status: value }));
      if (!entries.length) {
        throw new Error("Pilih minimal satu status sebelum menyimpan.");
      }
      const result = await api.put(`/academic/meetings/${meetingId}/attendance`, { entries });
      app.notify(result?.detail ?? "Koreksi tersimpan.");
      app.reload();
    },
  }).addEventListener("click", (event) => {
    const button = event.target.closest("[data-bulk]");
    if (!button) return;
    event.preventDefault();
    const value = button.dataset.bulk;
    document.querySelectorAll('.aps-drawer select[name^="status-"]').forEach((select) => {
      select.value = value;
    });
  });
}

export default {
  title: "Absensi",

  async render(app) {
    app.paint(skeletonTable(8));
    const [classes, subjects, response] = await Promise.all([
      app.classes(),
      app.subjects(),
      api.get(
        `/console/attendance${query({
          date: state.date,
          class_id: state.classId,
          subject_id: state.subjectId,
          attendance_status: state.status,
          source: state.source,
          limit: 300,
        })}`,
      ),
    ]);
    state.rows = response.items ?? [];

    const table = state.rows.length
      ? `<div class="aps-tablewrap aps-tablewrap--tall"><table class="aps-table">
          <thead><tr>
            <th>Tanggal</th><th>Kelas</th><th>Mata Pelajaran</th><th>Jam</th>
            <th>Siswa</th><th class="aps-center">Status</th><th class="aps-center">Akurasi</th><th>Waktu Catat</th><th>Sumber</th>
          </tr></thead>
          <tbody>${state.rows
            .map(
              (row) => `<tr>
                <td>${row.date ? esc(fmtDate(row.date)) : "—"}</td>
                <td>${esc(row.class_code ?? "—")}</td>
                <td><span class="aps-strong">${esc(row.subject_name ?? "—")}</span><span class="aps-sub">Pertemuan ${row.meeting_number ?? "-"}</span></td>
                <td>${esc(fmtRange(row.start_time, row.end_time))}</td>
                <td><span class="aps-strong">${esc(row.student_name ?? "—")}</span><span class="aps-sub">${esc(row.student_id ?? "")}</span></td>
                <td class="aps-center">${attendanceCode(row.status)}</td>
                <td class="aps-center">${accuracyCell(row.match_score)}</td>
                <td>${esc(fmtDateTime(row.recorded_at))}</td>
                <td>${row.source === "face" ? badge("Face Recognition", "brand") : badge("Manual", "neutral")}</td>
              </tr>`,
            )
            .join("")}</tbody>
        </table></div>
        ${legend()}`
      : emptyState({
          title: "Belum ada data absensi",
          description:
            "Kehadiran tercatat otomatis saat kamera mengenali siswa pada jadwal yang aktif. Gunakan Koreksi Absensi bila perlu menyesuaikan.",
        });

    app.paint(`
      <div class="aps-toolbar">
        <button class="aps-btn aps-btn--ghost" data-act="correct" type="button">${icon("attendance")} Koreksi Absensi</button>
        ${
          app.isLecturer
            ? ""
            : `<button class="aps-btn aps-btn--ghost" data-act="sync-face" type="button">${icon("camera")} Tarik Absensi Wajah</button>`
        }
        <div class="aps-toolbar-spacer"></div>
        <span class="aps-hint">${response.total ?? state.rows.length} catatan</span>
      </div>
      <div class="aps-filters">
        <span class="aps-filters-label">Filter</span>
        <label class="aps-field"><span>Tanggal</span><input type="date" data-filter="date" value="${esc(state.date)}" /></label>
        ${selectField("Kelas", "classId", classes.map((item) => ({ value: item.class_id, label: item.class_code })), state.classId, { allLabel: "Semua" })}
        ${selectField("Mapel", "subjectId", subjects.map((item) => ({ value: item.subject_id, label: item.subject_name })), state.subjectId, { allLabel: "Semua" })}
        ${selectField(
          "Status",
          "status",
          Object.entries(ATTENDANCE_LABELS).map(([code, label]) => ({ value: code, label: `${code} · ${label}` })),
          state.status,
          { allLabel: "Semua" },
        )}
        ${selectField(
          "Sumber",
          "source",
          [
            { value: "face", label: "Face Recognition" },
            { value: "manual", label: "Manual" },
          ],
          state.source,
          { allLabel: "Semua" },
        )}
      </div>
      ${table}`);
  },

  mount(app) {
    const host = app.content();

    host.querySelectorAll("[data-filter]").forEach((field) =>
      field.addEventListener("change", () => {
        state[field.dataset.filter] = field.value;
        app.reload();
      }),
    );

    // Scans taken before a jadwal had any pertemuan never reached the recap.
    // This files them so the percentages catch up.
    host.querySelector("[data-act=sync-face]")?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        const result = await api.post("/console/attendance/sync-face");
        app.notify(result?.detail ?? "Absensi wajah ditarik.");
        app.reload();
      } catch (error) {
        app.notify(error?.message ?? "Penarikan gagal.", "danger");
        button.disabled = false;
      }
    });

    host.querySelector("[data-act=correct]")?.addEventListener("click", async () => {
      const response = await api.get(`/academic/schedules${query({ class_id: state.classId })}`);
      const schedules = response.items ?? [];
      if (!schedules.length) {
        app.notify("Belum ada jadwal untuk dikoreksi.", "danger");
        return;
      }
      showDrawer({
        title: "Koreksi Absensi",
        description: "Pilih jadwal, lalu pertemuan yang ingin dikoreksi.",
        submitLabel: "Lanjut",
        body: `<label>Jadwal
          <select name="schedule_id">
            ${schedules
              .map(
                (item) =>
                  `<option value="${esc(item.schedule_id)}">${esc(item.class_code ?? "")} · ${esc(item.subject_name ?? "")}</option>`,
              )
              .join("")}
          </select>
        </label>`,
        async onSubmit(values) {
          const schedule = schedules.find((item) => item.schedule_id === values.schedule_id);
          await sheetDrawer(app, schedule);
        },
      });
    });
  },
};
