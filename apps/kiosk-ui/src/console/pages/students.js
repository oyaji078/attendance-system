/* Siswa — six columns, one search, two filters, one kebab per row.
 * Everything else (address, email, face data, history) lives on the detail
 * page, so the list stays scannable. */

import { api, query } from "../api.js";
import {
  badge,
  confirmDialog,
  emptyState,
  esc,
  icon,
  kebab,
  patch,
  searchBox,
  selectField,
  showDrawer,
  showMenu,
  skeletonTable,
  statusBadge,
} from "../ui.js";

const state = { search: "", classId: "", status: "active" };

function enrollmentBadge(person) {
  return person.primary_template_id
    ? badge("Aktif", "success")
    : person.sample_count > 0
      ? badge("Perlu ulang", "warning")
      : badge("Belum", "neutral");
}

function matches(person) {
  if (state.classId && person.class_id !== state.classId) return false;
  if (state.status === "active" && !person.is_active) return false;
  if (state.status === "inactive" && person.is_active) return false;
  const needle = state.search.trim().toLowerCase();
  if (!needle) return true;
  return (
    String(person.full_name ?? "").toLowerCase().includes(needle) ||
    String(person.student_id ?? "").toLowerCase().includes(needle)
  );
}

async function studentDrawer(app, person = null) {
  const classes = await app.classes();
  const isEdit = Boolean(person);
  showDrawer({
    title: isEdit ? "Edit Siswa" : "Tambah Siswa",
    description: isEdit ? esc(person.full_name) : "Setelah disimpan, tempatkan siswa ke kelas lewat Kelola Kelas.",
    submitLabel: "Simpan",
    body: `
      <label>NISN <span class="aps-hint">Kosongkan untuk dibuat otomatis</span>
        <input name="student_id" value="${esc(person?.student_id ?? "")}" placeholder="Otomatis" />
      </label>
      <label>Nama Lengkap
        <input name="full_name" value="${esc(person?.full_name ?? "")}" required />
      </label>
      <label>Alamat
        <input name="address" value="${esc(person?.address ?? "")}" />
      </label>
      <label>Email <span class="aps-hint">Opsional</span>
        <input name="email" type="email" value="${esc(person?.email ?? "")}" />
      </label>
      <label>Kelas
        <select name="class_id">
          <option value="">Belum ditempatkan</option>
          ${classes
            .map(
              (item) =>
                `<option value="${esc(item.class_id)}"${item.class_id === person?.class_id ? " selected" : ""}>${esc(item.class_code)} — ${esc(item.class_name)}</option>`,
            )
            .join("")}
        </select>
      </label>`,
    async onSubmit(values) {
      let studentId = values.student_id?.trim();
      if (!studentId) {
        const chosen = classes.find((item) => item.class_id === values.class_id);
        const next = await api.get(
          `/admin/ids/next${query({ entity: "student", class_code: chosen?.class_code ?? "AUTO" })}`,
        );
        studentId = next.id;
      }
      const payload = {
        student_id: studentId,
        full_name: values.full_name.trim(),
        address: values.address?.trim() || null,
        email: values.email?.trim() || null,
        class_id: values.class_id || null,
        is_active: person?.is_active ?? false,
      };
      if (isEdit) await api.put(`/admin/persons/${person.person_id}`, payload);
      else await api.post("/admin/persons", payload);

      // Keep the enrollment record in step with the class picked here.
      if (payload.class_id) {
        const target = isEdit ? person.person_id : (await findByStudentId(studentId))?.person_id;
        if (target) {
          await api.put(`/console/students/${target}/enrollments`, {
            class_id: payload.class_id,
            status: "active",
          });
        }
      }
      app.invalidate("classes");
      app.notify(isEdit ? "Data siswa disimpan." : "Siswa ditambahkan.");
      app.reload();
    },
  });
}

async function findByStudentId(studentId) {
  const response = await api.get("/admin/persons?limit=100");
  return (response.items ?? []).find((item) => item.student_id === studentId) ?? null;
}

async function enrollmentDrawer(app, person) {
  const [classes, current] = await Promise.all([
    app.classes(),
    api.get(`/console/students/${person.person_id}/enrollments`),
  ]);
  const active = (current.items ?? []).find((item) => item.status === "active");
  showDrawer({
    title: "Kelola Kelas",
    description: `${person.full_name} · ${person.student_id}`,
    submitLabel: "Simpan",
    body: `
      <label>Kelas
        <select name="class_id" required>
          <option value="">Pilih kelas</option>
          ${classes
            .map(
              (item) =>
                `<option value="${esc(item.class_id)}"${item.class_id === (active?.class_id ?? person.class_id) ? " selected" : ""}>${esc(item.class_code)} — ${esc(item.class_name)}</option>`,
            )
            .join("")}
        </select>
      </label>
      <label>Status
        <select name="status">
          <option value="active"${active?.status === "inactive" ? "" : " selected"}>Aktif</option>
          <option value="inactive"${active?.status === "inactive" ? " selected" : ""}>Nonaktif</option>
        </select>
      </label>
      <label>Tanggal Mulai
        <input name="start_date" type="date" value="${esc(active?.start_date ?? "")}" />
      </label>
      <label>Catatan <span class="aps-hint">Opsional</span>
        <input name="note" value="${esc(active?.note ?? "")}" maxlength="255" />
      </label>
      ${
        (current.items ?? []).length
          ? `<div><p class="aps-hint" style="margin:0 0 var(--s-2)">Riwayat</p>
              ${(current.items ?? [])
                .map(
                  (item) =>
                    `<div style="display:flex;gap:var(--s-2);align-items:center;font-size:var(--t-sm);padding:var(--s-1) 0">
                      ${item.status === "active" ? badge("Aktif", "success") : badge("Selesai", "neutral")}
                      <span>${esc(item.class_code ?? "-")}</span>
                      <span class="aps-hint">${esc(item.start_date ?? "-")}${item.end_date ? ` → ${esc(item.end_date)}` : ""}</span>
                    </div>`,
                )
                .join("")}
            </div>`
          : ""
      }`,
    async onSubmit(values) {
      await api.put(`/console/students/${person.person_id}/enrollments`, {
        class_id: values.class_id,
        status: values.status,
        start_date: values.start_date || null,
        note: values.note?.trim() || null,
      });
      app.invalidate("classes");
      app.notify("Enrollment kelas diperbarui.");
      app.reload();
    },
  });
}

/** The table region only. Kept separate so typing filters in place. */
function listHtml() {
  const visible = (state.rows ?? []).filter(matches);
  if (!visible.length) {
    return emptyState({
      title: state.rows?.length ? "Tidak ada siswa yang cocok" : "Belum ada siswa",
      description: state.rows?.length
        ? "Ubah kata kunci atau filter untuk melihat siswa lain."
        : "Tambahkan siswa, lalu tempatkan ke kelas melalui Kelola Kelas.",
    });
  }
  return `<div class="aps-tablewrap">
    <table class="aps-table">
      <thead><tr>
        <th>NISN</th><th>Nama</th><th>Kelas</th>
        <th>Status</th><th>Enrollment</th><th class="aps-actions"></th>
      </tr></thead>
      <tbody>
        ${visible
          .map(
            (person) => `<tr data-person="${esc(person.person_id)}">
              <td>${esc(person.student_id)}</td>
              <td><button class="aps-strong" data-open="${esc(person.person_id)}" type="button"
                  style="border:0;background:none;padding:0;font:inherit;font-weight:600;color:var(--c-brand);cursor:pointer">${esc(person.full_name)}</button></td>
              <td>${esc(person.class_code ?? "—")}</td>
              <td>${statusBadge(person.is_active)}</td>
              <td>${enrollmentBadge(person)}</td>
              <td class="aps-actions">${kebab(person.person_id)}</td>
            </tr>`,
          )
          .join("")}
      </tbody>
    </table>
  </div>`;
}

export default {
  title: "Siswa",

  async render(app) {
    app.paint(skeletonTable(8));
    const [people, classes] = await Promise.all([api.get("/admin/persons?limit=100"), app.classes()]);
    state.rows = people.items ?? [];

    const visible = state.rows.filter(matches);

    app.paint(`
      <div class="aps-toolbar">
        ${app.isLecturer ? "" : `<button class="aps-btn" data-act="add" type="button">${icon("plus")} Tambah Siswa</button>`}
        <div class="aps-toolbar-spacer"></div>
        ${searchBox(state.search, "Cari nama atau NISN")}
      </div>
      <div class="aps-filters">
        <span class="aps-filters-label">Filter</span>
        ${selectField("Kelas", "classId", classes.map((item) => ({ value: item.class_id, label: item.class_code })), state.classId, { allLabel: "Semua" })}
        ${selectField(
          "Status",
          "status",
          [
            { value: "active", label: "Aktif" },
            { value: "inactive", label: "Nonaktif" },
          ],
          state.status,
          { allLabel: "Semua" },
        )}
        <div class="aps-toolbar-spacer"></div>
        <span class="aps-hint" data-role="count">${visible.length} dari ${state.rows.length} siswa</span>
      </div>
      <div data-role="list">${listHtml()}</div>`);
  },

  mount(app) {
    const host = app.content();

    host.querySelector("[data-act=add]")?.addEventListener("click", () => studentDrawer(app));

    // Filtering is local to the rows already fetched, so it repaints only the
    // table — the search input is never replaced and keeps focus and caret.
    const repaint = () => {
      patch(host, "[data-role=list]", `<div data-role="list">${listHtml()}</div>`);
      const count = host.querySelector("[data-role=count]");
      if (count) {
        count.textContent = `${(state.rows ?? []).filter(matches).length} dari ${(state.rows ?? []).length} siswa`;
      }
      bindRows();
    };

    const search = host.querySelector("[data-role=search]");
    search?.addEventListener("input", () => {
      state.search = search.value;
      repaint();
    });

    host.querySelectorAll("[data-filter]").forEach((select) =>
      select.addEventListener("change", () => {
        state[select.dataset.filter] = select.value;
        repaint();
      }),
    );

    function bindRows() {
    host.querySelectorAll("[data-open]").forEach((button) =>
      button.addEventListener("click", () => app.navigate("student-detail", { personId: button.dataset.open })),
    );

    host.querySelectorAll("[data-kebab]").forEach((button) =>
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        const person = state.rows.find((item) => item.person_id === button.dataset.kebab);
        if (!person) return;
        const items = [
          { label: "Lihat", icon: "eye", onSelect: () => app.navigate("student-detail", { personId: person.person_id }) },
        ];
        if (!app.isLecturer) {
          items.push(
            { label: "Edit", icon: "pencil", onSelect: () => studentDrawer(app, person) },
            { label: "Pindah Kelas", icon: "swap", onSelect: () => enrollmentDrawer(app, person) },
            "-",
            person.is_active
              ? {
                  label: "Nonaktifkan",
                  icon: "power",
                  danger: true,
                  onSelect: async () => {
                    const ok = await confirmDialog({
                      title: "Nonaktifkan siswa?",
                      message: `${person.full_name} tidak lagi muncul di daftar aktif. Riwayat absensi tetap tersimpan.`,
                      confirmLabel: "Nonaktifkan",
                      danger: true,
                    });
                    if (!ok) return;
                    await api.patch(`/admin/persons/${person.person_id}/deactivate`);
                    app.notify("Siswa dinonaktifkan.");
                    app.reload();
                  },
                }
              : {
                  label: "Aktifkan",
                  icon: "power",
                  onSelect: async () => {
                    await api.patch(`/admin/persons/${person.person_id}/reactivate`);
                    app.notify("Siswa diaktifkan kembali.");
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
