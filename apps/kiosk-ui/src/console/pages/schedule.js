/* Jadwal — a timetable, not a list of forms.
 * Rows are time slots, columns are days, cells are clickable. Clicking an empty
 * cell opens a drawer pre-filled with that day and hour; clicking a filled one
 * edits it. */

import { api, query } from "../api.js";
import {
  DAY_LABELS,
  confirmDialog,
  emptyState,
  esc,
  fmtRange,
  icon,
  kebab,
  selectField,
  showDrawer,
  showMenu,
  skeletonTable,
} from "../ui.js";

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];

const state = { classId: "", academicYear: "", semester: "", rows: [] };

function currentAcademicYear() {
  const now = new Date();
  const start = now.getMonth() + 1 >= 7 ? now.getFullYear() : now.getFullYear() - 1;
  return `${start}/${start + 1}`;
}

/** Time slots come from the schedules themselves, so the grid matches reality
 *  instead of assuming a fixed 07:00–15:00 school day. */
function slotsFrom(schedules) {
  const seen = new Map();
  for (const item of schedules) {
    if (!item.start_time) continue;
    const key = `${String(item.start_time).slice(0, 5)}-${String(item.end_time ?? "").slice(0, 5)}`;
    if (!seen.has(key)) seen.set(key, { start: item.start_time, end: item.end_time, key });
  }
  return [...seen.values()].sort((a, b) => String(a.start).localeCompare(String(b.start)));
}

async function scheduleDrawer(app, { schedule = null, day = "", start = "", end = "" } = {}) {
  const [classes, subjects, lecturers] = await Promise.all([app.classes(), app.subjects(), app.lecturers()]);
  const isEdit = Boolean(schedule);

  showDrawer({
    title: isEdit ? "Edit Jadwal" : "Tambah Jadwal",
    description: isEdit ? `${schedule.class_code} · ${schedule.subject_name}` : "Kelas, mata pelajaran, guru, dan waktu.",
    submitLabel: "Simpan",
    body: `
      <div class="aps-form-row">
        <label>Kelas
          <select name="class_id" required>
            <option value="">Pilih kelas</option>
            ${classes
              .map(
                (item) =>
                  `<option value="${esc(item.class_id)}"${item.class_id === (schedule?.class_id ?? state.classId) ? " selected" : ""}>${esc(item.class_code)}</option>`,
              )
              .join("")}
          </select>
        </label>
        <label>Mata Pelajaran
          <select name="subject_id" required>
            <option value="">Pilih mata pelajaran</option>
            ${subjects
              .filter((item) => item.is_active || item.subject_id === schedule?.subject_id)
              .map(
                (item) =>
                  `<option value="${esc(item.subject_id)}"${item.subject_id === schedule?.subject_id ? " selected" : ""}>${esc(item.subject_name)}</option>`,
              )
              .join("")}
          </select>
        </label>
      </div>
      <label>Guru Pengampu
        <select name="lecturer_id">
          <option value="">Belum ditentukan</option>
          ${lecturers
            .map(
              (item) =>
                `<option value="${esc(item.lecturer_id)}"${item.lecturer_id === schedule?.lecturer_id ? " selected" : ""}>${esc(item.full_name)}</option>`,
            )
            .join("")}
        </select>
      </label>
      <div class="aps-form-row">
        <label>Hari
          <select name="day_of_week">
            <option value="">—</option>
            ${DAYS.map(
              (value) =>
                `<option value="${value}"${value === (schedule?.day_of_week ?? day) ? " selected" : ""}>${DAY_LABELS[value]}</option>`,
            ).join("")}
          </select>
        </label>
        <label>Ruangan
          <input name="room" value="${esc(schedule?.room ?? "")}" />
        </label>
      </div>
      <div class="aps-form-row">
        <label>Jam Mulai
          <input name="start_time" type="time" value="${esc(String(schedule?.start_time ?? start).slice(0, 5))}" />
        </label>
        <label>Jam Selesai
          <input name="end_time" type="time" value="${esc(String(schedule?.end_time ?? end).slice(0, 5))}" />
        </label>
      </div>
      <div class="aps-form-row">
        <label>Tahun Ajaran
          <input name="academic_year" value="${esc(schedule?.academic_year ?? state.academicYear ?? currentAcademicYear())}" required />
        </label>
        <label>Semester
          <select name="semester">
            <option value="ganjil"${schedule?.semester === "genap" ? "" : " selected"}>Ganjil</option>
            <option value="genap"${schedule?.semester === "genap" ? " selected" : ""}>Genap</option>
          </select>
        </label>
      </div>
      <label>Jumlah Pertemuan <span class="aps-hint">Menentukan kolom P1..Pn pada rekap</span>
        <input name="total_meetings" type="number" min="1" max="60" value="${schedule?.total_meetings ?? 16}" />
      </label>
      <label style="flex-direction:row;align-items:center;gap:var(--s-2)">
        <input name="with_kiosk_session" type="checkbox" ${schedule && !schedule.session_code ? "" : "checked"} style="min-height:auto;width:16px" />
        <span>Aktifkan absensi wajah untuk jadwal ini</span>
      </label>`,
    async onSubmit(values) {
      const payload = {
        class_id: values.class_id,
        subject_id: values.subject_id,
        lecturer_id: values.lecturer_id || null,
        academic_year: values.academic_year.trim(),
        semester: values.semester,
        day_of_week: values.day_of_week || null,
        start_time: values.start_time || null,
        end_time: values.end_time || null,
        total_meetings: Number(values.total_meetings || 16),
        room: values.room?.trim() || null,
        is_active: true,
        with_kiosk_session: values.with_kiosk_session === "on",
      };
      if (isEdit) await api.put(`/academic/schedules/${schedule.schedule_id}`, payload);
      else await api.post("/academic/schedules", payload);
      app.invalidate("schedules");
      app.notify(isEdit ? "Jadwal disimpan." : "Jadwal ditambahkan.");
      app.reload();
    },
  });
}

export default {
  title: "Jadwal",

  async render(app) {
    app.paint(skeletonTable(6));
    if (app.params.classId && !state.classId) state.classId = app.params.classId;

    const [classes, response, filters] = await Promise.all([
      app.classes(),
      api.get(
        `/academic/schedules${query({
          class_id: state.classId,
          academic_year: state.academicYear,
          semester: state.semester,
        })}`,
      ),
      api.get("/academic/schedules/filters").catch(() => ({ academic_years: [] })),
    ]);
    const schedules = response.items ?? [];
    state.rows = schedules;

    const slots = slotsFrom(schedules);
    const unscheduled = schedules.filter((item) => !item.day_of_week || !item.start_time);

    const grid = slots.length
      ? `<div class="aps-timetable">
          <table>
            <thead><tr>
              <th class="aps-tt-time">Jam</th>
              ${DAYS.map((day) => `<th>${DAY_LABELS[day]}</th>`).join("")}
            </tr></thead>
            <tbody>
              ${slots
                .map(
                  (slot) => `<tr>
                    <td class="aps-tt-time">${esc(fmtRange(slot.start, slot.end))}</td>
                    ${DAYS.map((day) => {
                      const item = schedules.find(
                        (row) =>
                          row.day_of_week === day &&
                          String(row.start_time ?? "").slice(0, 5) === String(slot.start).slice(0, 5),
                      );
                      if (!item) {
                        return `<td><button class="aps-tt-cell" data-new-day="${day}" data-new-start="${esc(String(slot.start).slice(0, 5))}" data-new-end="${esc(String(slot.end ?? "").slice(0, 5))}" type="button">
                          <span class="aps-tt-empty">+ Tambah</span>
                        </button></td>`;
                      }
                      return `<td style="position:relative">
                        <button class="aps-tt-cell aps-tt-cell--filled" data-edit="${esc(item.schedule_id)}" type="button">
                          <strong>${esc(item.subject_name ?? "-")}</strong>
                          <span>${esc(item.class_code ?? "")}${item.room ? ` · ${esc(item.room)}` : ""}</span>
                          <span>${esc(item.lecturer_name ?? "Guru belum ditentukan")}</span>
                        </button>
                        <span class="aps-tt-menu">${kebab(item.schedule_id)}</span>
                      </td>`;
                    }).join("")}
                  </tr>`,
                )
                .join("")}
            </tbody>
          </table>
        </div>`
      : emptyState({
          title: "Belum ada jadwal",
          description: "Tambahkan jadwal dengan hari dan jam agar tampil pada tabel mingguan.",
          action: `<button class="aps-btn" data-act="add" type="button">${icon("plus")} Tambah Jadwal</button>`,
        });

    // Sessions no jadwal owns — made before schedules existed, or left behind by
    // a deleted one. They still drive Mode Absensi, so they must stay reachable.
    let orphans = [];
    if (!app.isLecturer) {
      const owned = new Set(schedules.map((item) => item.attendance_session_id).filter(Boolean));
      const all = await api.get("/admin/attendance-sessions?include_deleted=false").catch(() => ({ items: [] }));
      orphans = (all.items ?? []).filter((item) => !item.is_deleted && !owned.has(item.session_id));
    }
    state.orphans = orphans;

    const orphanPanel = orphans.length
      ? `<section class="aps-card">
          <div class="aps-card-head"><div style="flex:1 1 auto">
            <h2>Sesi Absensi Tanpa Jadwal</h2>
            <p>Sesi lama yang belum terhubung ke jadwal. Tetap dipakai Mode Absensi di kios.</p>
          </div><span class="aps-badge">${orphans.length}</span></div>
          <div class="aps-tablewrap" style="border:0;border-radius:0;box-shadow:none">
            <table class="aps-table">
              <thead><tr><th>Kode</th><th>Nama</th><th>Kelas</th><th>Status</th><th class="aps-actions"></th></tr></thead>
              <tbody>${orphans
                .map(
                  (item) => `<tr>
                    <td class="aps-strong">${esc(item.session_code)}</td>
                    <td>${esc(item.session_name)}</td>
                    <td>${esc(item.class_name ?? item.class_code ?? "—")}</td>
                    <td>${item.is_active ? `<span class="aps-badge aps-badge--success">Aktif</span>` : `<span class="aps-badge">Nonaktif</span>`}</td>
                    <td class="aps-actions">${kebab(`session:${item.session_id}`)}</td>
                  </tr>`,
                )
                .join("")}</tbody>
            </table>
          </div>
        </section>`
      : "";

    const pending = unscheduled.length
      ? `<section class="aps-card">
          <div class="aps-card-head"><div>
            <h2>Tanpa hari / jam</h2>
            <p>Jadwal ini belum punya slot mingguan, jadi belum muncul di tabel.</p>
          </div></div>
          <div class="aps-card-body" style="display:flex;flex-wrap:wrap;gap:var(--s-2)">
            ${unscheduled
              .map(
                (item) =>
                  `<button class="aps-btn aps-btn--ghost aps-btn--sm" data-edit="${esc(item.schedule_id)}" type="button">
                    ${esc(item.class_code ?? "")} · ${esc(item.subject_name ?? "")}
                  </button>`,
              )
              .join("")}
          </div>
        </section>`
      : "";

    app.paint(`
      <div class="aps-toolbar">
        ${app.isLecturer ? "" : `<button class="aps-btn" data-act="add" type="button">${icon("plus")} Tambah Jadwal</button>`}
        <div class="aps-toolbar-spacer"></div>
        <span class="aps-hint">${schedules.length} jadwal</span>
      </div>
      <div class="aps-filters">
        <span class="aps-filters-label">Filter</span>
        ${selectField("Kelas", "classId", classes.map((item) => ({ value: item.class_id, label: item.class_code })), state.classId, { allLabel: "Semua" })}
        ${selectField(
          "Tahun Ajaran",
          "academicYear",
          (filters.academic_years ?? []).map((year) => ({ value: year, label: year })),
          state.academicYear,
          { allLabel: "Semua" },
        )}
        ${selectField(
          "Semester",
          "semester",
          [
            { value: "ganjil", label: "Ganjil" },
            { value: "genap", label: "Genap" },
          ],
          state.semester,
          { allLabel: "Semua" },
        )}
      </div>
      ${grid}
      ${pending}
      ${orphanPanel}`);
  },

  mount(app) {
    const host = app.content();

    host.querySelectorAll("[data-act=add]").forEach((button) =>
      button.addEventListener("click", () => scheduleDrawer(app)),
    );

    host.querySelectorAll("[data-filter]").forEach((select) =>
      select.addEventListener("change", () => {
        state[select.dataset.filter] = select.value;
        app.reload();
      }),
    );

    host.querySelectorAll("[data-new-day]").forEach((cell) =>
      cell.addEventListener("click", () => {
        if (app.isLecturer) return;
        scheduleDrawer(app, {
          day: cell.dataset.newDay,
          start: cell.dataset.newStart,
          end: cell.dataset.newEnd,
        });
      }),
    );

    host.querySelectorAll("[data-kebab]").forEach((button) =>
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        const key = button.dataset.kebab;
        if (key.startsWith("session:")) {
          const session = (state.orphans ?? []).find((row) => row.session_id === key.slice(8));
          if (!session) return;
          showMenu(button, [
            {
              label: "Salin Kode",
              icon: "copy",
              onSelect: async () => {
                await navigator.clipboard?.writeText?.(session.session_code);
                app.notify("Kode sesi disalin.");
              },
            },
            {
              label: session.is_active ? "Nonaktifkan" : "Aktifkan",
              icon: "power",
              danger: session.is_active,
              onSelect: async () => {
                const action = session.is_active ? "deactivate" : "activate";
                await api.patch(`/admin/attendance-sessions/${session.session_id}/${action}`);
                app.notify(session.is_active ? "Sesi dinonaktifkan." : "Sesi diaktifkan.");
                app.reload();
              },
            },
          ]);
          return;
        }
        const schedule = state.rows.find((row) => row.schedule_id === key);
        if (!schedule) return;
        const items = [
          {
            label: "Absensi",
            icon: "attendance",
            onSelect: () => app.navigate("attendance", { scheduleId: schedule.schedule_id }),
          },
          {
            label: "Rekap",
            icon: "recap",
            onSelect: () => app.navigate("recap-subject", { scheduleId: schedule.schedule_id }),
          },
        ];
        if (!app.isLecturer) {
          items.push(
            { label: "Edit", icon: "pencil", onSelect: () => scheduleDrawer(app, { schedule }) },
            "-",
            {
              label: schedule.is_active ? "Nonaktifkan" : "Aktifkan",
              icon: "power",
              onSelect: async () => {
                const action = schedule.is_active ? "deactivate" : "reactivate";
                await api.patch(`/academic/schedules/${schedule.schedule_id}/${action}`);
                app.invalidate("schedules");
                app.notify(schedule.is_active ? "Jadwal dinonaktifkan." : "Jadwal diaktifkan kembali.");
                app.reload();
              },
            },
            {
              label: "Hapus",
              icon: "trash",
              danger: true,
              onSelect: async () => {
                // Deleting takes the meetings and their attendance with it, so
                // the confirmation says exactly how much data that is.
                const held = schedule.held_meeting_count ?? 0;
                const ok = await confirmDialog({
                  title: "Hapus jadwal ini?",
                  message:
                    `${schedule.class_code ?? ""} · ${schedule.subject_name ?? ""} akan dihapus permanen ` +
                    `beserta ${schedule.meeting_count ?? 0} pertemuan` +
                    (held ? ` (${held} sudah terlaksana)` : "") +
                    ` dan seluruh data absensinya. Gunakan Nonaktifkan bila datanya masih diperlukan.`,
                  confirmLabel: "Hapus permanen",
                  danger: true,
                });
                if (!ok) return;
                const result = await api.delete(`/academic/schedules/${schedule.schedule_id}`);
                app.invalidate("schedules");
                app.notify(result?.detail ?? "Jadwal dihapus.");
                app.reload();
              },
            },
          );
        }
        showMenu(button, items);
      }),
    );

    host.querySelectorAll("[data-edit]").forEach((cell) =>
      cell.addEventListener("click", () => {
        const schedule = state.rows.find((row) => row.schedule_id === cell.dataset.edit);
        if (!schedule) return;
        if (app.isLecturer) {
          app.navigate("attendance", { scheduleId: schedule.schedule_id });
          return;
        }
        scheduleDrawer(app, { schedule });
      }),
    );
  },
};
