/* Mata Pelajaran — one subject, many classes.
 * The "Kelas" column shows which classes use it, so nobody creates "Matematika
 * X IPA 1" and "Matematika X IPA 2" as separate subjects. */

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

const state = { search: "", rows: [], usage: {} };

async function subjectDrawer(app, item = null) {
  const isEdit = Boolean(item);
  showDrawer({
    title: isEdit ? "Edit Mata Pelajaran" : "Tambah Mata Pelajaran",
    submitLabel: "Simpan",
    body: `
      <label>Kode <span class="aps-hint">Kosongkan untuk dibuat otomatis</span>
        <input name="subject_code" value="${esc(item?.subject_code ?? "")}" placeholder="PWEB-01" />
      </label>
      <label>Nama Mata Pelajaran
        <input name="subject_name" value="${esc(item?.subject_name ?? "")}" placeholder="Matematika" required />
      </label>
      <label>Keterangan <span class="aps-hint">Opsional</span>
        <input name="description" value="${esc(item?.description ?? "")}" />
      </label>`,
    async onSubmit(values) {
      const payload = {
        subject_code: values.subject_code?.trim() || null,
        subject_name: values.subject_name.trim(),
        description: values.description?.trim() || null,
        is_active: item?.is_active ?? true,
      };
      if (isEdit) await api.put(`/academic/subjects/${item.subject_id}`, payload);
      else await api.post("/academic/subjects", payload);
      app.invalidate("subjects", "schedules");
      app.notify(isEdit ? "Mata pelajaran disimpan." : "Mata pelajaran ditambahkan.");
      app.reload();
    },
  });
}

/** The table region only, so search can repaint it in place. */
function listHtml() {
  const needle = state.search.trim().toLowerCase();
  const visible = needle
    ? (state.rows ?? []).filter(
        (item) =>
          String(item.subject_name ?? "").toLowerCase().includes(needle) ||
          String(item.subject_code ?? "").toLowerCase().includes(needle),
      )
    : state.rows ?? [];
  if (!visible.length) {
    return emptyState({
      title: state.rows?.length ? "Tidak ada mata pelajaran yang cocok" : "Belum ada mata pelajaran",
      description: state.rows?.length
        ? "Ubah kata kunci pencarian."
        : "Tambahkan mata pelajaran, lalu hubungkan ke kelas melalui Jadwal.",
    });
  }
  return `<div class="aps-tablewrap"><table class="aps-table">
    <thead><tr><th>Kode</th><th>Mata Pelajaran</th><th>Diajarkan di Kelas</th><th>Status</th><th class="aps-actions"></th></tr></thead>
    <tbody>${visible
      .map((item) => {
        const classes = state.usage[item.subject_id] ?? [];
        return `<tr>
          <td class="aps-strong">${esc(item.subject_code)}</td>
          <td>${esc(item.subject_name)}${item.description ? `<span class="aps-sub">${esc(item.description)}</span>` : ""}</td>
          <td>${classes.length ? esc(classes.join(", ")) : `<span class="aps-sub">Belum dijadwalkan</span>`}</td>
          <td>${statusBadge(item.is_active)}</td>
          <td class="aps-actions">${kebab(item.subject_id)}</td>
        </tr>`;
      })
      .join("")}</tbody>
  </table></div>`;
}

export default {
  title: "Mata Pelajaran",

  async render(app) {
    app.paint(skeletonTable(6));
    const [subjects, schedules] = await Promise.all([
      app.subjects({ refresh: true }),
      api.get("/academic/schedules"),
    ]);
    state.rows = subjects;

    // Which classes each subject is taught to — the relation that makes one
    // subject reusable across classes.
    state.usage = {};
    for (const schedule of schedules.items ?? []) {
      const list = (state.usage[schedule.subject_id] ??= []);
      if (schedule.class_code && !list.includes(schedule.class_code)) list.push(schedule.class_code);
    }

    app.paint(`
      <div class="aps-toolbar">
        <button class="aps-btn" data-act="add" type="button">${icon("plus")} Tambah Mata Pelajaran</button>
        <div class="aps-toolbar-spacer"></div>
        ${searchBox(state.search, "Cari mata pelajaran")}
      </div>
      <div data-role="list">${listHtml()}</div>`);
  },

  mount(app) {
    const host = app.content();
    host.querySelector("[data-act=add]")?.addEventListener("click", () => subjectDrawer(app));

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
        const item = state.rows.find((row) => row.subject_id === button.dataset.kebab);
        if (!item) return;
        showMenu(button, [
          { label: "Edit", icon: "pencil", onSelect: () => subjectDrawer(app, item) },
          "-",
          item.is_active
            ? {
                label: "Nonaktifkan",
                icon: "power",
                danger: true,
                onSelect: async () => {
                  const ok = await confirmDialog({
                    title: "Nonaktifkan mata pelajaran?",
                    message: `${item.subject_name} tidak dapat dipilih untuk jadwal baru. Jadwal dan rekap yang sudah ada tetap utuh.`,
                    confirmLabel: "Nonaktifkan",
                    danger: true,
                  });
                  if (!ok) return;
                  await api.patch(`/academic/subjects/${item.subject_id}/deactivate`);
                  app.invalidate("subjects");
                  app.notify("Mata pelajaran dinonaktifkan.");
                  app.reload();
                },
              }
            : {
                label: "Aktifkan",
                icon: "power",
                onSelect: async () => {
                  await api.patch(`/academic/subjects/${item.subject_id}/reactivate`);
                  app.invalidate("subjects");
                  app.notify("Mata pelajaran diaktifkan kembali.");
                  app.reload();
                },
              },
        ]);
      }),
    );
    }

    bindRows();
  },
};
