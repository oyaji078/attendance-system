/* Console shell: fixed sidebar, fixed header, scrollable content, and a small
 * hash-free router. Pages are plain objects with `title`, `render(ctx)` and an
 * optional `mount(ctx)`; the shell owns layout, navigation and shared state so
 * a page only worries about its own screen. */

import { api, setUnauthorizedHandler } from "./api.js";
import { closeDrawer, closeMenu, esc, icon, initials, toast } from "./ui.js";

import dashboardPage from "./pages/dashboard.js";
import studentsPage from "./pages/students.js";
import studentDetailPage from "./pages/student-detail.js";
import classesPage from "./pages/classes.js";
import classDetailPage from "./pages/class-detail.js";
import subjectsPage from "./pages/subjects.js";
import schedulePage from "./pages/schedule.js";
import attendancePage from "./pages/attendance.js";
import recapSubjectPage from "./pages/recap-subject.js";
import recapClassPage from "./pages/recap-class.js";
import usersPage from "./pages/users.js";
import settingsPage from "./pages/settings.js";

const PAGES = {
  dashboard: dashboardPage,
  students: studentsPage,
  "student-detail": studentDetailPage,
  classes: classesPage,
  "class-detail": classDetailPage,
  subjects: subjectsPage,
  schedule: schedulePage,
  attendance: attendancePage,
  "recap-subject": recapSubjectPage,
  "recap-class": recapClassPage,
  users: usersPage,
  settings: settingsPage,
};

// Sidebar stays short on purpose: four sections, no "Laporan"/"Statistik"/
// "Data Master" duplicates of what these already cover.
const NAV = [
  { type: "item", route: "dashboard", label: "Dashboard", icon: "dashboard" },
  { type: "group", label: "Akademik" },
  { type: "item", route: "students", label: "Siswa", icon: "students" },
  { type: "item", route: "classes", label: "Kelas", icon: "classes" },
  { type: "item", route: "subjects", label: "Mata Pelajaran", icon: "subjects", adminOnly: true },
  { type: "item", route: "schedule", label: "Jadwal", icon: "schedule" },
  { type: "group", label: "Absensi" },
  { type: "item", route: "attendance", label: "Absensi", icon: "attendance" },
  { type: "item", route: "recap-subject", label: "Rekap", icon: "recap", children: true },
  { type: "sub", route: "recap-subject", label: "Per Mata Pelajaran" },
  { type: "sub", route: "recap-class", label: "Per Kelas" },
  { type: "group", label: "Sistem", adminOnly: true },
  { type: "item", route: "users", label: "Pengguna", icon: "users", adminOnly: true },
  { type: "item", route: "settings", label: "Pengaturan", icon: "settings", adminOnly: true },
];

const LECTURER_ROUTES = new Set(["dashboard", "schedule", "attendance", "recap-subject", "recap-class"]);

export class Console {
  constructor(root, { user, onExit, onLogout, onOpenKiosk }) {
    this.root = root;
    this.user = user;
    this.onExit = onExit;
    this.onLogout = onLogout;
    this.onOpenKiosk = onOpenKiosk;
    this.route = "dashboard";
    this.params = {};
    this.settings = {};
    // Reference data most pages filter by; fetched once, refreshed on demand.
    this.cache = { classes: null, subjects: null, lecturers: null, schedules: null };
    this.history = [];
  }

  get isLecturer() {
    return this.user?.role === "lecturer";
  }

  canSee(route) {
    return this.isLecturer ? LECTURER_ROUTES.has(route) : true;
  }

  /* --------------------------- reference data --------------------------- */

  async classes({ refresh = false } = {}) {
    if (refresh || !this.cache.classes) {
      if (this.isLecturer) {
        // /admin/* is admin-only. A guru's class list is exactly the classes
        // they teach, which their own schedules already name.
        const schedules = await api.get("/academic/schedules");
        const seen = new Map();
        for (const item of schedules.items ?? []) {
          if (item.class_id && !seen.has(item.class_id)) {
            seen.set(item.class_id, {
              class_id: item.class_id,
              class_code: item.class_code,
              class_name: item.class_name,
              lecturer_name: item.lecturer_name,
              is_active: true,
            });
          }
        }
        this.cache.classes = [...seen.values()];
      } else {
        const response = await api.get("/admin/classes?limit=100");
        this.cache.classes = response.items ?? [];
      }
    }
    return this.cache.classes;
  }

  async subjects({ refresh = false } = {}) {
    if (refresh || !this.cache.subjects) {
      const response = await api.get("/academic/subjects?limit=200");
      this.cache.subjects = response.items ?? [];
    }
    return this.cache.subjects;
  }

  async lecturers({ refresh = false } = {}) {
    if (refresh || !this.cache.lecturers) {
      // Only admins manage teachers, and only admin pages ask for this list.
      if (this.isLecturer) return (this.cache.lecturers = []);
      const response = await api.get("/admin/lecturers?limit=100");
      this.cache.lecturers = response.items ?? [];
    }
    return this.cache.lecturers;
  }

  async schedules({ refresh = false, params = "" } = {}) {
    if (refresh || !this.cache.schedules) {
      const response = await api.get(`/academic/schedules${params}`);
      this.cache.schedules = response.items ?? [];
    }
    return this.cache.schedules;
  }

  invalidate(...keys) {
    for (const key of keys) this.cache[key] = null;
  }

  /* ------------------------------ routing ------------------------------- */

  navigate(route, params = {}, { replace = false } = {}) {
    if (!PAGES[route] || !this.canSee(route)) route = this.canSee("dashboard") ? "dashboard" : "schedule";
    if (!replace && this.route) {
      this.history.push({ route: this.route, params: this.params });
      if (this.history.length > 20) this.history.shift();
    }
    this.route = route;
    this.params = params;
    closeMenu();
    closeDrawer();
    this.renderShell();
    this.renderPage();
  }

  back() {
    const previous = this.history.pop();
    if (previous) {
      this.route = previous.route;
      this.params = previous.params;
      this.renderShell();
      this.renderPage();
    } else {
      this.navigate("dashboard", {}, { replace: true });
    }
  }

  reload() {
    this.renderPage();
  }

  /* ------------------------------ rendering ----------------------------- */

  async start() {
    setUnauthorizedHandler(() => this.onLogout?.());
    this.root.innerHTML = "";
    // `aps` carries the design tokens, `aps-shell` the sidebar/header layout.
    this.root.className = "aps aps-shell";
    this.root.dataset.nav = "closed";
    try {
      this.settings = (await api.get("/console/settings")) ?? {};
    } catch {
      this.settings = {};
    }
    this.renderShell();
    this.renderPage();
  }

  schoolName() {
    return this.settings?.school_name || "Sistem Absensi";
  }

  renderShell() {
    const page = PAGES[this.route] ?? PAGES.dashboard;
    const navHtml = NAV.filter((entry) => !entry.adminOnly || !this.isLecturer)
      .filter((entry) => entry.type !== "item" || this.canSee(entry.route))
      .filter((entry) => entry.type !== "sub" || this.canSee(entry.route))
      .map((entry) => {
        if (entry.type === "group") return `<p class="aps-nav-group">${esc(entry.label)}</p>`;
        if (entry.type === "sub") {
          return `<div class="aps-nav-sub"><button class="aps-nav-item" data-route="${entry.route}"${
            this.route === entry.route ? ' aria-current="page"' : ""
          } type="button">${esc(entry.label)}</button></div>`;
        }
        // The "Rekap" parent is a label for its two children, not a target.
        if (entry.children) {
          const active = this.route.startsWith("recap-");
          return `<div class="aps-nav-item" style="cursor:default;${active ? "color:var(--c-ink);font-weight:600" : ""}">${icon(entry.icon)}<span>${esc(entry.label)}</span></div>`;
        }
        return `<button class="aps-nav-item" data-route="${entry.route}"${
          this.route === entry.route ? ' aria-current="page"' : ""
        } type="button">${icon(entry.icon)}<span>${esc(entry.label)}</span></button>`;
      })
      .join("");

    const crumbs = typeof page.breadcrumb === "function" ? page.breadcrumb(this) : null;
    const title = typeof page.title === "function" ? page.title(this) : page.title;

    this.root.innerHTML = `
      <nav class="aps-sidebar" aria-label="Navigasi utama">
        <div class="aps-brand">
          <span class="aps-brand-mark">${esc(this.schoolName().slice(0, 2).toUpperCase())}</span>
          <span class="aps-brand-text">
            <strong>${esc(this.schoolName())}</strong>
            <span>Konsol Akademik</span>
          </span>
        </div>
        <div class="aps-nav">${navHtml}</div>
      </nav>
      <div class="aps-main">
        <header class="aps-header">
          <button class="aps-iconbtn aps-menu-toggle" data-act="toggle-nav" type="button" aria-label="Menu">${icon("menu", 18)}</button>
          <div class="aps-header-title">
            ${crumbs ? `<div class="aps-crumb">${crumbs}</div>` : ""}
            <h1>${esc(title)}</h1>
          </div>
          <div class="aps-header-actions">
            <button class="aps-btn aps-btn--ghost aps-btn--sm" data-act="kiosk" type="button">${icon("camera")} Mode Kios</button>
            <div class="aps-user">
              <span class="aps-avatar">${esc(initials(this.user?.full_name || this.user?.username))}</span>
              <span>${esc(this.user?.full_name || this.user?.username || "-")}</span>
            </div>
            <button class="aps-iconbtn" data-act="logout" type="button" aria-label="Keluar" title="Keluar">${icon("logout")}</button>
          </div>
        </header>
        <main class="aps-content" data-role="content" tabindex="-1"></main>
      </div>`;

    this.root.querySelectorAll("[data-route]").forEach((button) =>
      button.addEventListener("click", () => {
        this.root.dataset.nav = "closed";
        this.navigate(button.dataset.route);
      }),
    );
    this.root.querySelector("[data-act=toggle-nav]")?.addEventListener("click", () => {
      this.root.dataset.nav = this.root.dataset.nav === "open" ? "closed" : "open";
    });
    this.root.querySelector("[data-act=kiosk]")?.addEventListener("click", () => this.onExit?.());
    this.root.querySelector("[data-act=logout]")?.addEventListener("click", () => this.onLogout?.());
  }

  content() {
    return this.root.querySelector("[data-role=content]");
  }

  /** Replace the page body. Pages call this to re-render themselves. */
  paint(html) {
    const host = this.content();
    if (host) host.innerHTML = `<div class="aps-page">${html}</div>`;
  }

  async renderPage() {
    const page = PAGES[this.route] ?? PAGES.dashboard;
    const host = this.content();
    if (!host) return;
    const token = Symbol("render");
    this._token = token;
    try {
      await page.render(this);
      if (this._token !== token) return;
      await page.mount?.(this);
    } catch (error) {
      if (this._token !== token) return;
      this.paint(
        `<div class="aps-alert" role="alert"><span>${esc(error?.message ?? "Halaman gagal dimuat.")}</span>
         <button class="aps-btn aps-btn--ghost aps-btn--sm" data-act="retry" type="button">Coba lagi</button></div>`,
      );
      host.querySelector("[data-act=retry]")?.addEventListener("click", () => this.renderPage());
    }
  }

  notify(message, tone = "success") {
    toast(message, tone);
  }
}

export function mountConsole(root, options) {
  const app = new Console(root, options);
  app.start();
  return app;
}
