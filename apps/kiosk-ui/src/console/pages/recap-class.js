/* Rekap Per Kelas — summary, not a meeting matrix.
 *
 * One row per student, one column per subject the class takes, each cell the
 * attendance percentage for that subject. P1..Pn belongs on the per-subject
 * recap; mixing the two would make both harder to read. */

import { api, query } from "../api.js";
import { emptyState, esc, fmtPercent, icon, percentCell, selectField, skeletonTable } from "../ui.js";

const state = { classId: "", academicYear: "", semester: "" };

export default {
  title: "Rekap Per Kelas",

  async render(app) {
    app.paint(skeletonTable(8));

    if (app.params.classId) {
      state.classId = app.params.classId;
      app.params.classId = null;
    }

    const [classes, filters] = await Promise.all([
      app.classes(),
      api.get("/academic/schedules/filters").catch(() => ({ academic_years: [] })),
    ]);
    if (!state.classId && classes.length) state.classId = classes[0].class_id;

    const controls = `<div class="aps-filters">
      ${selectField("Kelas", "classId", classes.map((item) => ({ value: item.class_id, label: `${item.class_code} — ${item.class_name}` })), state.classId, { stack: true, allLabel: null })}
      ${selectField(
        "Tahun Ajaran",
        "academicYear",
        (filters.academic_years ?? []).map((year) => ({ value: year, label: year })),
        state.academicYear,
        { stack: true, allLabel: "Semua" },
      )}
      ${selectField(
        "Semester",
        "semester",
        [
          { value: "ganjil", label: "Ganjil" },
          { value: "genap", label: "Genap" },
        ],
        state.semester,
        { stack: true, allLabel: "Semua" },
      )}
      <div class="aps-toolbar-spacer"></div>
      <div style="align-self:end">
        <button class="aps-btn aps-btn--ghost aps-btn--sm" data-act="print" type="button">${icon("print")} Print</button>
      </div>
    </div>`;

    if (!classes.length) {
      app.paint(controls + emptyState({ title: "Belum ada kelas", description: "Tambahkan kelas terlebih dahulu." }));
      return;
    }

    const recap = await api.get(
      `/console/classes/${state.classId}/recap${query({
        academic_year: state.academicYear,
        semester: state.semester,
      })}`,
    );

    if (!recap.subjects.length) {
      app.paint(
        controls +
          emptyState({
            title: "Belum ada mata pelajaran pada periode ini",
            description: "Tambahkan jadwal untuk kelas ini agar rekap dapat dihitung.",
          }),
      );
      return;
    }
    if (!recap.rows.length) {
      app.paint(
        controls +
          emptyState({
            title: "Belum ada siswa di kelas ini",
            description: "Tempatkan siswa melalui menu Siswa → Kelola Kelas.",
          }),
      );
      return;
    }

    const head = `<tr>
      <th class="aps-sticky-1 aps-num">No</th>
      <th class="aps-sticky-2">NISN</th>
      <th class="aps-sticky-3">Nama</th>
      ${recap.subjects
        .map(
          (subject) =>
            `<th title="${esc(subject.subject_name)} — ${subject.held_meetings} dari ${subject.total_meetings} pertemuan terlaksana${
              subject.lecturer_name ? ` — ${subject.lecturer_name}` : ""
            }">${esc(subject.subject_name)}</th>`,
        )
        .join("")}
      <th>Rata-rata</th>
    </tr>`;

    const body = recap.rows
      .map(
        (row) => `<tr>
          <td class="aps-sticky-1 aps-num">${row.no}</td>
          <td class="aps-sticky-2">${esc(row.student_id)}</td>
          <td class="aps-sticky-3 aps-strong">${esc(row.full_name)}</td>
          ${row.percents.map((value) => `<td>${percentCell(value)}</td>`).join("")}
          <td>${percentCell(row.average_percent)}</td>
        </tr>`,
      )
      .join("");

    app.paint(`
      ${controls}
      <section class="aps-card"><div class="aps-card-body" style="padding:var(--s-4) var(--s-5)">
        <dl class="aps-facts">
          <div><dt>Kelas</dt><dd class="aps-strong">${esc(recap.class_code)} — ${esc(recap.class_name)}</dd></div>
          <div><dt>Jumlah Siswa</dt><dd>${recap.student_count}</dd></div>
          <div><dt>Mata Pelajaran</dt><dd>${recap.subjects.length}</dd></div>
          <div><dt>Rata-rata Kelas</dt><dd>${esc(fmtPercent(recap.average_percent))}</dd></div>
        </dl>
      </div></section>
      <div class="aps-tablewrap aps-tablewrap--tall">
        <table class="aps-table"><thead>${head}</thead><tbody>${body}</tbody></table>
      </div>
      <p class="aps-hint" style="margin:0">
        Setiap sel adalah persentase kehadiran siswa pada mata pelajaran tersebut.
        Tanda – berarti mata pelajaran itu belum memiliki pertemuan yang terlaksana.
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
    host.querySelector("[data-act=print]")?.addEventListener("click", () => window.print());
  },
};
