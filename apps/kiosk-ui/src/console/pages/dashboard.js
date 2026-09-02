/* Dashboard — four numbers that matter and what happened recently.
 * Deliberately no charts: staff open this to check today, not to analyse.
 *
 * The attendance log here is the last handful of rows, with the face-match
 * score next to each: it answers "is the camera still recognising people
 * properly" at a glance. The full, filterable log lives on Absensi. */

import { api } from "../api.js";
import {
  accuracyCell,
  attendanceCode,
  emptyState,
  esc,
  fmtDate,
  fmtDateTime,
  fmtPercent,
  icon,
  skeletonCards,
  skeletonTable,
} from "../ui.js";

export default {
  title: "Dashboard",

  async render(app) {
    app.paint(`${skeletonCards(4)}${skeletonTable(5)}`);

    const data = await api.get("/console/dashboard");

    const rate = data.today_total > 0 ? (data.today_present / data.today_total) * 100 : null;

    const stats = data.metrics
      .map(
        (metric) => `<div class="aps-stat">
          <dt>${esc(metric.label)}</dt>
          <dd>${metric.value}</dd>
          ${metric.hint ? `<small>${esc(metric.hint)}</small>` : ""}
        </div>`,
      )
      .join("");

    const todayCard = `<section class="aps-card">
      <div class="aps-card-head">
        <div style="flex:1 1 auto">
          <h2>Kehadiran Hari Ini</h2>
          <p>Dihitung dari pertemuan yang berlangsung hari ini.</p>
        </div>
        ${rate === null ? "" : `<span class="aps-badge aps-badge--brand">${esc(fmtPercent(rate))}</span>`}
      </div>
      <div class="aps-card-body">
        ${
          data.today_total === 0
            ? `<p style="margin:0;color:var(--c-muted)">Belum ada pertemuan yang tercatat hari ini.</p>`
            : `<div class="aps-stats">
                <div class="aps-stat"><dt>Hadir</dt><dd>${data.today_present}</dd></div>
                <div class="aps-stat"><dt>Tidak hadir</dt><dd>${data.today_absent}</dd></div>
                <div class="aps-stat"><dt>Total tercatat</dt><dd>${data.today_total}</dd></div>
              </div>`
        }
      </div>
    </section>`;

    const accuracy = data.accuracy ?? {};
    const threshold = (accuracy.threshold ?? 0.55) * 100;
    const accuracyCard = `<section class="aps-card">
      <div class="aps-card-head">
        <div style="flex:1 1 auto">
          <h2>Akurasi Pengenalan Wajah</h2>
          <p>${
            accuracy.scored
              ? `Kemiripan wajah pada absensi yang dicatat kamera, ${esc(fmtDate(accuracy.date))}.`
              : "Kemiripan wajah pada absensi yang dicatat kamera."
          }</p>
        </div>
        ${accuracy.average === null || accuracy.average === undefined ? "" : accuracyCell(accuracy.average)}
      </div>
      <div class="aps-card-body">
        ${
          accuracy.scored
            ? `<div class="aps-stats">
                <div class="aps-stat"><dt>Rata-rata</dt><dd>${esc(fmtPercent(accuracy.average * 100))}</dd></div>
                <div class="aps-stat"><dt>Terendah</dt><dd>${esc(fmtPercent(accuracy.lowest * 100))}</dd></div>
                <div class="aps-stat">
                  <dt>Perlu ditinjau</dt><dd>${accuracy.weak}</dd>
                  <small>Di bawah ${esc(fmtPercent(threshold))}</small>
                </div>
                <div class="aps-stat"><dt>Tercatat kamera</dt><dd>${accuracy.scored}</dd></div>
              </div>`
            : `<p style="margin:0;color:var(--c-muted)">Belum ada absensi yang tercatat dari kamera. Angka akurasi muncul setelah kehadiran pertama dikenali.</p>`
        }
      </div>
    </section>`;

    const activityBody = data.activity.length
      ? `<div class="aps-tablewrap">
          <table class="aps-table">
            <thead><tr>
              <th>Waktu</th><th>Siswa</th><th>Kelas</th><th>Mata Pelajaran</th>
              <th class="aps-center">Status</th><th class="aps-center">Akurasi</th><th>Sumber</th>
            </tr></thead>
            <tbody>
              ${data.activity
                .map(
                  (row) => `<tr>
                    <td>${esc(fmtDateTime(row.at))}</td>
                    <td><span class="aps-strong">${esc(row.student_name ?? "-")}</span><span class="aps-sub">${esc(row.student_id ?? "")}</span></td>
                    <td>${esc(row.class_code ?? "-")}</td>
                    <td>${esc(row.subject_name ?? "-")}</td>
                    <td class="aps-center">${attendanceCode(row.status)}</td>
                    <td class="aps-center">${accuracyCell(row.match_score)}</td>
                    <td>${row.source === "face" ? "Face Recognition" : "Manual"}</td>
                  </tr>`,
                )
                .join("")}
            </tbody>
          </table>
        </div>`
      : emptyState({
          title: "Belum ada absensi tercatat",
          description: "Baris muncul setelah kehadiran tercatat dari kamera atau koreksi manual.",
        });

    app.paint(`
      <div class="aps-stats">${stats}</div>
      ${todayCard}
      ${accuracyCard}
      <section>
        <div class="aps-card-head" style="border:0;padding:0 0 var(--s-3)">
          <div style="flex:1 1 auto">
            <h2>Log Absensi Terbaru</h2>
            <p>Kehadiran terakhir yang masuk, beserta akurasi pencocokan wajahnya.</p>
          </div>
          <button class="aps-btn aps-btn--ghost aps-btn--sm" data-act="open-attendance" type="button">
            ${icon("attendance")} Lihat Semua
          </button>
        </div>
        ${activityBody}
      </section>`);
  },

  mount(app) {
    // Buttons painted into the page are outside the shell's own nav wiring, so
    // this one routes by hand.
    app.content()
      .querySelector("[data-act=open-attendance]")
      ?.addEventListener("click", () => app.navigate("attendance"));
  },
};
