/* Kelas — the list. Opening a class goes to its detail page with tabs. */

import { api } from "../api.js";
import {
  confirmDialog,
  emptyState,
  esc,
  icon,
  kebab,
  patch,
  searchBox,
  showDrawer,
  showMenu,
  skeletonTable,
  statusBadge,
} from "../ui.js";

const state = { search: "", rows: [] };

async function classDrawer(app, item = null) {
  const lecturers = await app.lecturers();
  const isEdit = Boolean(item);
  showDrawer({
    title: isEdit ? "Edit Kelas" : "Tambah Kelas",
    submitLabel: "Simpan",
    body: `
      <label>Kode Kelas <span class="aps-hint">Kosongkan untuk dibuat otomatis</span>
        <input name="class_code" value="${esc(item?.class_code ?? "")}" placeholder="KLS-0001" />
      </label>
      <label>Nama Kelas
        <input name="class_name" value="${esc(item?.class_name ?? "")}" placeholder="X IPA 1" required />
      </label>
      <label>Wali Kelas
        <select name="lecturer_id">
          <option value="">Belum ditentukan</option>
          ${lecturers
            .map(
              (row) =>
                `<option value="${esc(row.lecturer_id)}"${row.lecturer_id === item?.lecturer_id ? " selected" : ""}>${esc(row.full_name)}</option>`,
            )
            .join("")}
        </select>
      </label>
      <label>Keterangan <span class="aps-hint">Opsional</span>
        <input name="description" value="${esc(item?.description ?? "")}" />
      </label>`,
    async onSubmit(values) {
      const payload = {
        class_code: values.class_code?.trim() || null,
        class_name: values.class_name.trim(),
        lecturer_id: values.lecturer_id || null,
        description: values.description?.trim() || null,
        is_active: item?.is_active ?? true,
      };
      if (isEdit) await api.put(`/admin/classes/${item.class_id}`, payload);
      else await api.post("/admin/classes", payload);
      app.invalidate("classes");
      app.notify(isEdit ? "Kelas disimpan." : "Kelas ditambahkan.");
      app.reload();
    },
  });
}

function visibleClasses() {
  const needle = state.search.trim().toLowerCase();
  if (!needle) return state.rows ?? [];
  return (state.rows ?? []).filter(
    (item) =>
      String(item.class_code ?? "").toLowerCase().includes(needle) ||
      String(item.class_name ?? "").toLowerCase().includes(needle),
  );
}

/** The table region only, so search can repaint it in place. */
function listHtml() {
  const visible = visibleClasses();
  if (!visible.length) {
    return emptyState({
      title: state.rows?.length ? "Tidak ada kelas yang cocok" : "Belum ada kelas",
      description: state.rows?.length
        ? "Ubah kata kunci pencarian."
        : "Tambahkan kelas untuk mulai menempatkan siswa.",
    });
  }
  return `<div class="aps-tablewrap"><table class="aps-table">
    <thead><tr>
      <th>Kelas</th><th>Wali Kelas</th><th class="aps-num">Jumlah Siswa</th>
      <th>Status</th><th class="aps-actions"></th>
    </tr></thead>
    <tbody>${visible
      .map(
        (item) => `<tr>
          <td><button data-open="${esc(item.class_id)}" type="button"
               style="border:0;background:none;padding:0;font:inherit;font-weight:600;color:var(--c-brand);cursor:pointer">${esc(item.class_code)}</button>
              <span class="aps-sub">${esc(item.class_name)}</span></td>
          <td>${esc(item.lecturer_name ?? "—")}</td>
          <td class="aps-num">${item.total_students ?? 0}</td>
          <td>${statusBadge(item.is_active)}</td>
          <td class="aps-actions">${kebab(item.class_id)}</td>
        </tr>`,
      )
      .join("")}</tbody>
  </table></div>`;
}

export default {
  title: "Kelas",

  async render(app) {
    app.paint(skeletonTable(6));
    const classes = await app.classes({ refresh: true });
    state.rows = classes;

    app.paint(`
      <div class="aps-toolbar">
        ${app.isLecturer ? "" : `<button class="aps-btn" data-act="add" type="button">${icon("plus")} Tambah Kelas</button>`}
        <div class="aps-toolbar-spacer"></div>
        ${searchBox(state.search, "Cari kelas")}
      </div>
      <div data-role="list">${listHtml()}</div>`);
  },

  mount(app) {
    const host = app.content();
    host.querySelector("[data-act=add]")?.addEventListener("click", () => classDrawer(app));

    const repaint = () => {
      patch(host, "[data-role=list]", `<div data-role="list">${listHtml()}</div>`);
      bindRows();
    };

    // Local filter over the rows already fetched: no refetch, and the input is
    // never replaced mid-typing.
    const search = host.querySelector("[data-role=search]");
    search?.addEventListener("input", () => {
      state.search = search.value;
      repaint();
    });

    function bindRows() {
    host.querySelectorAll("[data-open]").forEach((button) =>
      button.addEventListener("click", () => app.navigate("class-detail", { classId: button.dataset.open })),
    );

    host.querySelectorAll("[data-kebab]").forEach((button) =>
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        const item = state.rows.find((row) => row.class_id === button.dataset.kebab);
        if (!item) return;
        const items = [
          { label: "Lihat", icon: "eye", onSelect: () => app.navigate("class-detail", { classId: item.class_id }) },
        ];
        if (!app.isLecturer) {
          items.push(
            { label: "Edit", icon: "pencil", onSelect: () => classDrawer(app, item) },
            "-",
            item.is_active
              ? {
                  label: "Nonaktifkan",
                  icon: "power",
                  danger: true,
                  onSelect: async () => {
                    const ok = await confirmDialog({
                      title: "Nonaktifkan kelas?",
                      message: `${item.class_code} disembunyikan dari daftar aktif. Jadwal dan riwayat absensi tetap tersimpan.`,
                      confirmLabel: "Nonaktifkan",
                      danger: true,
                    });
                    if (!ok) return;
                    await api.patch(`/admin/classes/${item.class_id}/deactivate`);
                    app.invalidate("classes");
                    app.notify("Kelas dinonaktifkan.");
                    app.reload();
                  },
                }
              : {
                  label: "Aktifkan",
                  icon: "power",
                  onSelect: async () => {
                    await api.patch(`/admin/classes/${item.class_id}/reactivate`);
                    app.invalidate("classes");
                    app.notify("Kelas diaktifkan kembali.");
                    app.reload();
                  },
                },
          );
        }
        showMenu(button, items);
      }),
    );
    }

    bindRows();
  },
};
