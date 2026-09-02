/* Pengaturan — the few values that belong to the console itself, plus the
 * kiosk device thresholds that already lived in device_configs. */

import { api } from "../api.js";
import { emptyState, esc, fmtDateTime, skeletonTable } from "../ui.js";

export default {
  title: "Pengaturan",

  async render(app) {
    app.paint(skeletonTable(4));

    const [settings, devices, filters] = await Promise.all([
      api.get("/console/settings"),
      api.get("/admin/devices/configs").catch(() => []),
      api.get("/academic/schedules/filters").catch(() => ({ academic_years: [] })),
    ]);

    const years = filters.academic_years ?? [];

    const devicesCard = devices.length
      ? `<div class="aps-tablewrap"><table class="aps-table">
          <thead><tr><th>Perangkat</th><th>Lokasi</th><th class="aps-num">Kemiripan</th><th class="aps-num">Keaslian</th><th>Status</th></tr></thead>
          <tbody>${devices
            .map(
              (device) => `<tr>
                <td><span class="aps-strong">${esc(device.device_name)}</span><span class="aps-sub">${esc(device.device_code)}</span></td>
                <td>${esc(device.location_hint ?? "—")}</td>
                <td class="aps-num">${device.similarity_threshold}</td>
                <td class="aps-num">${device.liveness_threshold}</td>
                <td>${device.is_enabled ? `<span class="aps-badge aps-badge--success">Aktif</span>` : `<span class="aps-badge">Nonaktif</span>`}</td>
              </tr>`,
            )
            .join("")}</tbody>
        </table></div>`
      : emptyState({
          title: "Belum ada perangkat kios",
          description: "Perangkat terdaftar otomatis saat kios pertama kali digunakan.",
        });

    app.paint(`
      <section class="aps-card">
        <div class="aps-card-head"><div>
          <h2>Identitas & Periode</h2>
          <p>Nama sekolah tampil di sidebar. Periode default dipakai sebagai pilihan awal pada filter.</p>
        </div></div>
        <div class="aps-card-body">
          <form class="aps-form" data-role="settings" style="max-width:520px">
            <div class="aps-logo-field">
              <div class="aps-logo-preview" data-role="logo-preview">
                ${
                  settings.school_logo
                    ? `<img src="${esc(settings.school_logo)}" alt="Logo sekolah" />`
                    : `<span>Belum ada logo</span>`
                }
              </div>
              <div style="flex:1 1 auto;min-width:0">
                <p class="aps-hint" style="margin:0 0 var(--s-2)">
                  Logo tampil pada kop semua dokumen yang diexport (PDF dan Excel).
                  PNG atau JPEG, maksimal 300 KB.
                </p>
                <div style="display:flex;gap:var(--s-2);flex-wrap:wrap">
                  <label class="aps-btn aps-btn--ghost aps-btn--sm" style="flex-direction:row;font-weight:600">
                    Pilih Logo
                    <input type="file" accept="image/png,image/jpeg" data-role="logo-input" style="display:none" />
                  </label>
                  ${settings.school_logo ? `<button class="aps-btn aps-btn--ghost aps-btn--sm" data-act="clear-logo" type="button">Hapus Logo</button>` : ""}
                </div>
              </div>
            </div>
            <input type="hidden" name="school_logo" value="${esc(settings.school_logo ?? "")}" />
            <label>Nama Sekolah
              <input name="school_name" value="${esc(settings.school_name ?? "")}" placeholder="SMPN 1 Selong" maxlength="120" />
            </label>
            <div class="aps-form-row">
              <label>Tahun Ajaran Default
                <input name="default_academic_year" list="aps-years" value="${esc(settings.default_academic_year ?? "")}" placeholder="2026/2027" maxlength="16" />
                <datalist id="aps-years">${years.map((year) => `<option value="${esc(year)}"></option>`).join("")}</datalist>
              </label>
              <label>Semester Default
                <select name="default_semester">
                  <option value=""${settings.default_semester ? "" : " selected"}>—</option>
                  <option value="ganjil"${settings.default_semester === "ganjil" ? " selected" : ""}>Ganjil</option>
                  <option value="genap"${settings.default_semester === "genap" ? " selected" : ""}>Genap</option>
                </select>
              </label>
            </div>
            <div style="display:flex;gap:var(--s-3);align-items:center">
              <button class="aps-btn" type="submit">Simpan Pengaturan</button>
              ${settings.updated_at ? `<span class="aps-hint">Terakhir diubah ${esc(fmtDateTime(settings.updated_at))}</span>` : ""}
            </div>
          </form>
        </div>
      </section>

      <section>
        <div class="aps-card-head" style="border:0;padding:0 0 var(--s-3)"><div>
          <h2>Perangkat Kios</h2>
          <p>Ambang pengenalan wajah diatur per perangkat dari layar kios.</p>
        </div></div>
        ${devicesCard}
      </section>`);
  },

  mount(app) {
    const form = app.content().querySelector("[data-role=settings]");
    const logoInput = form?.querySelector("[data-role=logo-input]");
    const logoField = form?.querySelector('input[name="school_logo"]');
    const preview = form?.querySelector("[data-role=logo-preview]");

    // Read the file in the browser and submit it as a data URI: no upload
    // endpoint, no upload directory, and the server validates it before storing.
    logoInput?.addEventListener("change", () => {
      const file = logoInput.files?.[0];
      if (!file) return;
      if (!["image/png", "image/jpeg"].includes(file.type)) {
        app.notify("Logo harus berformat PNG atau JPEG.", "danger");
        logoInput.value = "";
        return;
      }
      if (file.size > 300 * 1024) {
        app.notify("Ukuran logo maksimal 300 KB.", "danger");
        logoInput.value = "";
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        logoField.value = String(reader.result ?? "");
        if (preview) preview.innerHTML = `<img src="${logoField.value}" alt="Logo sekolah" />`;
      };
      reader.onerror = () => app.notify("Logo gagal dibaca.", "danger");
      reader.readAsDataURL(file);
    });

    form?.querySelector("[data-act=clear-logo]")?.addEventListener("click", () => {
      logoField.value = "";
      if (preview) preview.innerHTML = `<span>Belum ada logo</span>`;
    });

    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const values = Object.fromEntries(new FormData(form).entries());
      try {
        const saved = await api.put("/console/settings", {
          school_name: values.school_name?.trim() || null,
          default_academic_year: values.default_academic_year?.trim() || null,
          default_semester: values.default_semester || null,
          school_logo: values.school_logo || null,
        });
        app.settings = saved;
        app.notify("Pengaturan disimpan.");
        // The school name lives in the sidebar, so redraw the shell too.
        app.renderShell();
        app.reload();
      } catch (error) {
        app.notify(error?.message ?? "Pengaturan gagal disimpan.", "danger");
      }
    });
  },
};
