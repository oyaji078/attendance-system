/* Pengguna — login accounts (admin / guru) and the teacher records behind them. */

import { api } from "../api.js";
import {
  badge,
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

const state = { tab: "accounts", search: "", accounts: [], lecturers: [] };

const ROLE_LABELS = { admin: "Admin", lecturer: "Guru", operator: "Operator" };

async function accountDrawer(app, item = null) {
  const lecturers = await app.lecturers();
  const isEdit = Boolean(item);
  showDrawer({
    title: isEdit ? "Edit Akun" : "Tambah Akun",
    submitLabel: "Simpan",
    body: `
      <label>Username
        <input name="username" value="${esc(item?.username ?? "")}" autocomplete="off" required />
      </label>
      <label>Nama Lengkap
        <input name="full_name" value="${esc(item?.full_name ?? "")}" required />
      </label>
      <label>Email <span class="aps-hint">Opsional</span>
        <input name="email" type="email" value="${esc(item?.email ?? "")}" />
      </label>
      <label>${isEdit ? "Password Baru" : "Password"} ${isEdit ? `<span class="aps-hint">Kosongkan bila tidak diganti</span>` : ""}
        <input name="password" type="password" autocomplete="new-password" ${isEdit ? "" : "required"} />
      </label>
      <label>Peran
        <select name="role" data-role-select>
          <option value="admin"${item?.role === "lecturer" ? "" : " selected"}>Admin</option>
          <option value="lecturer"${item?.role === "lecturer" ? " selected" : ""}>Guru</option>
        </select>
      </label>
      <label data-lecturer-field${item?.role === "lecturer" ? "" : ' style="display:none"'}>
        Data Guru <span class="aps-hint">Menentukan kelas yang dapat diakses</span>
        <select name="lecturer_id">
          <option value="">Pilih guru</option>
          ${lecturers
            .map(
              (row) =>
                `<option value="${esc(row.lecturer_id)}"${row.lecturer_id === item?.lecturer_id ? " selected" : ""}>${esc(row.full_name)}</option>`,
            )
            .join("")}
        </select>
      </label>`,
    async onSubmit(values) {
      const payload = {
        username: values.username.trim(),
        full_name: values.full_name.trim(),
        email: values.email?.trim() || null,
        role: values.role,
        lecturer_id: values.role === "lecturer" ? values.lecturer_id || null : null,
        is_active: item?.is_active ?? true,
      };
      if (values.password) payload.password = values.password;
      if (isEdit) await api.put(`/admin/users/${item.admin_id}`, payload);
      else await api.post("/admin/users", payload);
      app.notify(isEdit ? "Akun disimpan." : "Akun ditambahkan.");
      app.reload();
    },
  }).addEventListener("change", (event) => {
    if (!event.target.matches("[data-role-select]")) return;
    const field = document.querySelector(".aps-drawer [data-lecturer-field]");
    if (field) field.style.display = event.target.value === "lecturer" ? "" : "none";
  });
}

async function lecturerDrawer(app, item = null) {
  const isEdit = Boolean(item);
  showDrawer({
    title: isEdit ? "Edit Guru" : "Tambah Guru",
    submitLabel: "Simpan",
    body: `
      <label>NIP <span class="aps-hint">Kosongkan untuk dibuat otomatis</span>
        <input name="lecturer_code" value="${esc(item?.lecturer_code ?? "")}" />
      </label>
      <label>Nama Guru
        <input name="full_name" value="${esc(item?.full_name ?? "")}" required />
      </label>
      <label>Alamat
        <input name="address" value="${esc(item?.address ?? "")}" />
      </label>
      <div class="aps-form-row">
        <label>Golongan
          <input name="rank_grade" value="${esc(item?.rank_grade ?? "")}" placeholder="III/b" />
        </label>
        <label>Mata Pelajaran / Bidang
          <input name="department" value="${esc(item?.department ?? "")}" />
        </label>
      </div>
      <label>Email <span class="aps-hint">Opsional</span>
        <input name="email" type="email" value="${esc(item?.email ?? "")}" />
      </label>`,
    async onSubmit(values) {
      const payload = {
        lecturer_code: values.lecturer_code?.trim() || null,
        full_name: values.full_name.trim(),
        email: values.email?.trim() || null,
        department: values.department?.trim() || null,
        address: values.address?.trim() || null,
        rank_grade: values.rank_grade?.trim() || null,
        is_active: item?.is_active ?? true,
      };
      if (isEdit) await api.put(`/admin/lecturers/${item.lecturer_id}`, payload);
      else await api.post("/admin/lecturers", payload);
      app.invalidate("lecturers");
      app.notify(isEdit ? "Data guru disimpan." : "Guru ditambahkan.");
      app.reload();
    },
  });
}

function visibleRows() {
  const needle = state.search.trim().toLowerCase();
  const source = state.tab === "accounts" ? state.accounts : state.lecturers;
  if (!needle) return source;
  return source.filter((item) =>
    state.tab === "accounts"
      ? String(item.username).toLowerCase().includes(needle) ||
        String(item.full_name).toLowerCase().includes(needle)
      : String(item.full_name).toLowerCase().includes(needle) ||
        String(item.lecturer_code).toLowerCase().includes(needle),
  );
}

/** The table region only, so search can repaint it in place. */
function listHtml() {
  const rows = visibleRows();
  if (!rows.length) {
    return emptyState({
      title: state.tab === "accounts" ? "Belum ada akun" : "Belum ada data guru",
      description:
        state.tab === "accounts"
          ? "Tambahkan akun admin atau guru untuk memberi akses ke konsol."
          : "Tambahkan data guru sebelum membuat akun dengan peran Guru.",
    });
  }
  if (state.tab === "accounts") {
    return `<div class="aps-tablewrap"><table class="aps-table">
      <thead><tr><th>Username</th><th>Nama</th><th>Peran</th><th>Guru</th><th>Status</th><th class="aps-actions"></th></tr></thead>
      <tbody>${rows
        .map(
          (item) => `<tr>
            <td class="aps-strong">${esc(item.username)}</td>
            <td>${esc(item.full_name)}<span class="aps-sub">${esc(item.email ?? "")}</span></td>
            <td>${badge(ROLE_LABELS[item.role] ?? item.role, item.role === "admin" ? "brand" : "info")}</td>
            <td>${esc(item.lecturer_name ?? "—")}</td>
            <td>${statusBadge(item.is_active)}</td>
            <td class="aps-actions">${kebab(item.admin_id)}</td>
          </tr>`,
        )
        .join("")}</tbody>
    </table></div>`;
  }
  return `<div class="aps-tablewrap"><table class="aps-table">
    <thead><tr><th>NIP</th><th>Nama Guru</th><th>Alamat</th><th>Golongan</th><th>Status</th><th class="aps-actions"></th></tr></thead>
    <tbody>${rows
      .map(
        (item) => `<tr>
          <td class="aps-strong">${esc(item.lecturer_code)}</td>
          <td>${esc(item.full_name)}<span class="aps-sub">${esc(item.department ?? "")}</span></td>
          <td>${esc(item.address ?? "—")}</td>
          <td>${esc(item.rank_grade ?? "—")}</td>
          <td>${statusBadge(item.is_active)}</td>
          <td class="aps-actions">${kebab(item.lecturer_id)}</td>
        </tr>`,
      )
      .join("")}</tbody>
  </table></div>`;
}

export default {
  title: "Pengguna",

  async render(app) {
    app.paint(skeletonTable(6));
    const [accounts, lecturers] = await Promise.all([api.get("/admin/users"), app.lecturers({ refresh: true })]);
    state.accounts = accounts.items ?? [];
    state.lecturers = lecturers;

    const tabs = `<div class="aps-tabs" role="tablist">
      <button class="aps-tab" role="tab" data-tab="accounts" aria-selected="${state.tab === "accounts"}" type="button">Akun Login</button>
      <button class="aps-tab" role="tab" data-tab="lecturers" aria-selected="${state.tab === "lecturers"}" type="button">Data Guru</button>
    </div>`;

    app.paint(`
      <div class="aps-toolbar">
        <button class="aps-btn" data-act="add" type="button">${icon("plus")} ${state.tab === "accounts" ? "Tambah Akun" : "Tambah Guru"}</button>
        <div class="aps-toolbar-spacer"></div>
        ${searchBox(state.search, state.tab === "accounts" ? "Cari username atau nama" : "Cari nama atau NIP")}
      </div>
      ${tabs}
      <div data-role="list">${listHtml()}</div>`);
  },

  mount(app) {
    const host = app.content();

    host.querySelectorAll("[data-tab]").forEach((button) =>
      button.addEventListener("click", () => {
        state.tab = button.dataset.tab;
        state.search = "";
        app.reload();
      }),
    );

    host.querySelector("[data-act=add]")?.addEventListener("click", () =>
      state.tab === "accounts" ? accountDrawer(app) : lecturerDrawer(app),
    );

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
    host.querySelectorAll("[data-kebab]").forEach((button) =>
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        const id = button.dataset.kebab;
        if (state.tab === "accounts") {
          const item = state.accounts.find((row) => row.admin_id === id);
          if (!item) return;
          showMenu(button, [
            { label: "Edit", icon: "pencil", onSelect: () => accountDrawer(app, item) },
            "-",
            item.is_active
              ? {
                  label: "Nonaktifkan",
                  icon: "power",
                  danger: true,
                  onSelect: async () => {
                    const ok = await confirmDialog({
                      title: "Nonaktifkan akun?",
                      message: `${item.username} tidak dapat masuk lagi sampai diaktifkan kembali.`,
                      confirmLabel: "Nonaktifkan",
                      danger: true,
                    });
                    if (!ok) return;
                    await api.patch(`/admin/users/${item.admin_id}/deactivate`);
                    app.notify("Akun dinonaktifkan.");
                    app.reload();
                  },
                }
              : {
                  label: "Aktifkan",
                  icon: "power",
                  onSelect: async () => {
                    await api.patch(`/admin/users/${item.admin_id}/reactivate`);
                    app.notify("Akun diaktifkan kembali.");
                    app.reload();
                  },
                },
          ]);
        } else {
          const item = state.lecturers.find((row) => row.lecturer_id === id);
          if (!item) return;
          showMenu(button, [
            { label: "Edit", icon: "pencil", onSelect: () => lecturerDrawer(app, item) },
            "-",
            item.is_active
              ? {
                  label: "Nonaktifkan",
                  icon: "power",
                  danger: true,
                  onSelect: async () => {
                    const ok = await confirmDialog({
                      title: "Nonaktifkan guru?",
                      message: `${item.full_name} tidak dapat dipilih untuk jadwal baru. Jadwal yang sudah ada tetap utuh.`,
                      confirmLabel: "Nonaktifkan",
                      danger: true,
                    });
                    if (!ok) return;
                    await api.patch(`/admin/lecturers/${item.lecturer_id}/deactivate`);
                    app.invalidate("lecturers");
                    app.notify("Guru dinonaktifkan.");
                    app.reload();
                  },
                }
              : {
                  label: "Aktifkan",
                  icon: "power",
                  onSelect: async () => {
                    await api.patch(`/admin/lecturers/${item.lecturer_id}/reactivate`);
                    app.invalidate("lecturers");
                    app.notify("Guru diaktifkan kembali.");
                    app.reload();
                  },
                },
          ]);
        }
      }),
    );
    }

    bindRows();
  },
};
