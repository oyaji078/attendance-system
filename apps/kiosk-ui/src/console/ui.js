/* Component primitives for the console.
 *
 * Every page builds from these, so a table, a badge, a drawer or an empty state
 * looks and behaves the same everywhere. Rendering is string-based (matching the
 * rest of this codebase) with delegated events, except for the overlays which
 * need real nodes. */

export function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

/* ------------------------------- icons ---------------------------------- */

const ICON_PATHS = {
  dashboard: "M4 13h6V4H4v9Zm0 7h6v-5H4v5Zm10 0h6V11h-6v9Zm0-16v5h6V4h-6Z",
  students: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm0 2c-4 0-8 2-8 4.5V21h16v-2.5C20 16 16 14 12 14Z",
  classes: "M4 5h16v3H4V5Zm0 5h16v3H4v-3Zm0 5h10v3H4v-3Z",
  subjects: "M6 3h9l5 5v13H6V3Zm8 1.5V9h4.5L14 4.5ZM8 12h8v1.6H8V12Zm0 4h8v1.6H8V16Z",
  schedule: "M7 2v2H5a2 2 0 0 0-2 2v14h18V6a2 2 0 0 0-2-2h-2V2h-2v2H9V2H7Zm12 8v9H5v-9h14Z",
  attendance: "M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2Z",
  recap: "M4 4h16v2H4V4Zm0 5h10v2H4V9Zm0 5h16v2H4v-2Zm0 5h10v2H4v-2Z",
  users: "M16 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM8 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm0 2c-3.3 0-6 1.7-6 3.8V20h12v-2.2C14 15.7 11.3 14 8 14Zm8 .3c-.6 0-1.2 0-1.7.2 1 .9 1.7 2 1.7 3.3V20h6v-2c0-2-2.6-3.7-6-3.7Z",
  settings:
    "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm9.4 4a7.5 7.5 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7.6 7.6 0 0 0-2-1.2L16.5 3h-4l-.4 2.6c-.7.3-1.4.7-2 1.2l-2.4-1-2 3.4 2 1.6a7.5 7.5 0 0 0 0 2.4l-2 1.6 2 3.4 2.4-1c.6.5 1.3.9 2 1.2l.4 2.6h4l.4-2.6c.7-.3 1.4-.7 2-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2Z",
  kebab: "M12 8a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm0 6a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm0 6a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
  search: "M10 3a7 7 0 1 0 4.2 12.6l4.1 4.1 1.4-1.4-4.1-4.1A7 7 0 0 0 10 3Zm0 2a5 5 0 1 1 0 10A5 5 0 0 1 10 5Z",
  plus: "M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5Z",
  back: "M15.4 7.4 14 6l-6 6 6 6 1.4-1.4L10.8 12l4.6-4.6Z",
  menu: "M3 6h18v2H3V6Zm0 5h18v2H3v-2Zm0 5h18v2H3v-2Z",
  close: "M18.3 5.7 12 12l6.3 6.3-1.4 1.4L10.6 13.4 4.3 19.7 2.9 18.3 9.2 12 2.9 5.7 4.3 4.3l6.3 6.3 6.3-6.3 1.4 1.4Z",
  empty: "M4 6h16v12H4V6Zm2 2v8h12V8H6Z",
  logout: "M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h5v-2H5V5h5V3Zm5.6 3.6L14.2 8l3 3H8v2h9.2l-3 3 1.4 1.4L21 12l-5.4-5.4Z",
  camera: "M9 4 7.2 6H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-3.2L15 4H9Zm3 5a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9Z",
  download: "M11 4h2v7h3.5L12 15.5 7.5 11H11V4ZM5 18h14v2H5v-2Z",
  print: "M7 3h10v4H7V3ZM5 8h14a2 2 0 0 1 2 2v6h-4v5H7v-5H3v-6a2 2 0 0 1 2-2Zm4 8h6v3H9v-3Z",
  eye: "M12 5c-5 0-9 4.5-9 7s4 7 9 7 9-4.5 9-7-4-7-9-7Zm0 11a4 4 0 1 1 0-8 4 4 0 0 1 0 8Zm0-2a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
  pencil: "M4 17.2V20h2.8L17 9.8 14.2 7 4 17.2ZM20.7 7.1a1 1 0 0 0 0-1.4l-2.4-2.4a1 1 0 0 0-1.4 0l-1.5 1.5 2.8 2.8 1.5-1.5Z",
  swap: "M8 3 4 7l4 4V8h8V6H8V3Zm8 18 4-4-4-4v3H8v2h8v3Z",
  power: "M13 3h-2v9h2V3Zm4.8 2.2-1.4 1.4A6.5 6.5 0 1 1 7.6 6.6L6.2 5.2a8.5 8.5 0 1 0 11.6 0Z",
  trash: "M9 3h6l1 2h4v2H4V5h4l1-2ZM6 8h12l-1 12H7L6 8Z",
  copy: "M8 2h9a2 2 0 0 1 2 2v11h-2V4H8V2ZM5 6h9a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2Z",
};

export function icon(name, size = 16) {
  const path = ICON_PATHS[name];
  if (!path) return "";
  return `<svg class="aps-ico" width="${size}" height="${size}" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="${path}"/></svg>`;
}

/* ------------------------------ formatting ------------------------------ */

const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const MONTHS_LONG = [
  "Januari", "Februari", "Maret", "April", "Mei", "Juni",
  "Juli", "Agustus", "September", "Oktober", "November", "Desember",
];

export const DAY_LABELS = {
  monday: "Senin",
  tuesday: "Selasa",
  wednesday: "Rabu",
  thursday: "Kamis",
  friday: "Jumat",
  saturday: "Sabtu",
  sunday: "Minggu",
};

function toDate(value) {
  if (!value) return null;
  const parsed = value instanceof Date ? value : new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function fmtDateShort(value) {
  const date = toDate(value);
  if (!date) return "-";
  return `${String(date.getDate()).padStart(2, "0")} ${MONTHS_SHORT[date.getMonth()]}`;
}

export function fmtDate(value) {
  const date = toDate(value);
  if (!date) return "-";
  return `${date.getDate()} ${MONTHS_LONG[date.getMonth()]} ${date.getFullYear()}`;
}

export function fmtTime(value) {
  if (!value) return "-";
  const text = String(value);
  if (/^\d{2}:\d{2}/.test(text)) return text.slice(0, 5);
  const date = toDate(value);
  if (!date) return "-";
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

export function fmtDateTime(value) {
  const date = toDate(value);
  if (!date) return "-";
  return `${fmtDate(date)} ${fmtTime(date)}`;
}

export function fmtRange(start, end) {
  if (!start && !end) return "-";
  return `${fmtTime(start)}–${fmtTime(end)}`;
}

export function fmtPercent(value) {
  if (value === null || value === undefined) return "-";
  const rounded = Math.round(Number(value) * 10) / 10;
  return `${rounded % 1 === 0 ? rounded.toFixed(0) : rounded.toFixed(1)}%`;
}

export function initials(name) {
  const parts = String(name ?? "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return (parts[0][0] + (parts[1]?.[0] ?? "")).toUpperCase();
}

/* ------------------------------ components ------------------------------ */

export function badge(label, tone = "neutral") {
  const cls = tone && tone !== "neutral" ? ` aps-badge--${tone}` : "";
  return `<span class="aps-badge${cls}">${esc(label)}</span>`;
}

export function statusBadge(isActive, activeLabel = "Aktif", inactiveLabel = "Nonaktif") {
  return isActive ? badge(activeLabel, "success") : badge(inactiveLabel, "neutral");
}

export function attendanceCode(code) {
  if (!code) return `<span class="aps-code aps-code--empty">–</span>`;
  return `<span class="aps-code aps-code--${esc(code)}" title="${esc(ATTENDANCE_LABELS[code] ?? code)}">${esc(code)}</span>`;
}

export const ATTENDANCE_LABELS = { H: "Hadir", S: "Sakit", I: "Izin", A: "Alpa" };

export function percentCell(value) {
  if (value === null || value === undefined) {
    return `<span class="aps-code aps-code--empty">–</span>`;
  }
  const numeric = Number(value);
  const tone = numeric < 60 ? " aps-pct--low" : numeric < 80 ? " aps-pct--mid" : "";
  return `<span class="aps-pct${tone}"><span class="aps-pct-bar"><i style="width:${Math.max(2, Math.min(100, numeric))}%"></i></span>${fmtPercent(numeric)}</span>`;
}

/* How well the face matched when the camera filed the row, 0..1.
 *
 * The tones follow the recognition thresholds rather than the recap's 60/80
 * grading: a genuine match sits above ~0.55, so anything under that is worth a
 * second look even though it was accepted, and there is no "failing" score here
 * — a rejected scan never became a row in the first place. */
export function accuracyCell(value) {
  if (value === null || value === undefined) {
    // Manual entry, or a scan filed before the score was kept - either way
    // there is no number to stand behind, and Sumber already says which.
    return `<span class="aps-acc aps-acc--none" title="Tanpa pencocokan wajah">-</span>`;
  }
  const percent = Math.max(0, Math.min(100, Number(value) * 100));
  const tone = percent >= 75 ? " aps-acc--high" : percent >= 55 ? "" : " aps-acc--low";
  return `<span class="aps-acc${tone}" title="Kemiripan wajah saat absensi tercatat">${fmtPercent(percent)}</span>`;
}

export function legend() {
  return `<div class="aps-legend">
    ${Object.entries(ATTENDANCE_LABELS)
      .map(([code, label]) => `<span>${attendanceCode(code)} ${esc(label)}</span>`)
      .join("")}
    <span><span class="aps-code aps-code--empty">–</span> Belum dilaksanakan</span>
  </div>`;
}

export function emptyState({ title, description = "", action = "" }) {
  return `<div class="aps-empty">
    ${icon("empty", 28)}
    <h3>${esc(title)}</h3>
    ${description ? `<p>${esc(description)}</p>` : ""}
    ${action}
  </div>`;
}

export function errorState(message, { retry = true } = {}) {
  return `<div class="aps-alert" role="alert">
    <span>${esc(message)}</span>
    ${retry ? `<button class="aps-btn aps-btn--ghost aps-btn--sm" data-act="retry" type="button">Coba lagi</button>` : ""}
  </div>`;
}

export function skeletonTable(rows = 6) {
  return `<div class="aps-card"><div class="aps-card-body"><div class="aps-skeleton">
    ${Array.from({ length: rows }, () => `<div class="aps-skel aps-skel--row"></div>`).join("")}
  </div></div></div>`;
}

export function skeletonCards(count = 4) {
  return `<div class="aps-stats">
    ${Array.from({ length: count }, () => `<div class="aps-skel aps-skel--card"></div>`).join("")}
  </div>`;
}

export function kebab(id) {
  return `<button class="aps-iconbtn" data-kebab="${esc(id)}" type="button" aria-label="Aksi lainnya" title="Aksi lainnya">${icon("kebab")}</button>`;
}

export function searchBox(value, placeholder) {
  return `<div class="aps-search">${icon("search")}
    <input type="search" data-role="search" value="${esc(value ?? "")}" placeholder="${esc(placeholder)}" aria-label="${esc(placeholder)}" />
  </div>`;
}

export function selectField(label, name, options, selected, { stack = false, allLabel = null } = {}) {
  const items = allLabel === null ? options : [{ value: "", label: allLabel }, ...options];
  return `<label class="aps-field${stack ? " aps-field--stack" : ""}"><span>${esc(label)}</span>
    <select data-filter="${esc(name)}" name="${esc(name)}">
      ${items
        .map(
          (item) =>
            `<option value="${esc(item.value)}"${String(item.value) === String(selected ?? "") ? " selected" : ""}>${esc(item.label)}</option>`,
        )
        .join("")}
    </select>
  </label>`;
}

/* ------------------------------- overlays ------------------------------- */

/** Replace one region of the page without re-rendering (and re-focusing) the
 *  rest. List pages use it so typing in the search box never steals the caret. */
export function patch(host, selector, html) {
  const node = host?.querySelector(selector);
  if (node) node.outerHTML = html;
}

let openMenu = null;

export function closeMenu() {
  if (openMenu) {
    openMenu.remove();
    openMenu = null;
  }
}

export function showMenu(anchor, items) {
  closeMenu();
  const menu = document.createElement("div");
  // `aps` matters: the menu lives on <body>, so it needs the token scope or
  // every var(--c-*) below resolves to nothing and it renders transparent.
  menu.className = "aps-menu aps";
  menu.setAttribute("role", "menu");
  menu.innerHTML = items
    .map((item) =>
      item === "-"
        ? "<hr />"
        : `<button type="button" role="menuitem" class="${item.danger ? "is-danger" : ""}" data-menu-index="${items.indexOf(item)}">${
            item.icon ? icon(item.icon, 15) : ""
          }<span>${esc(item.label)}</span></button>`,
    )
    .join("");
  document.body.appendChild(menu);

  const rect = anchor.getBoundingClientRect();
  const width = menu.offsetWidth;
  const height = menu.offsetHeight;
  // Flip when the trigger sits near the viewport edge so the menu never opens
  // off-screen on the last row of a long table.
  const left = Math.min(Math.max(8, rect.right - width), window.innerWidth - width - 8);
  const below = rect.bottom + 4;
  const top = below + height > window.innerHeight - 8 ? Math.max(8, rect.top - height - 4) : below;
  menu.style.left = `${left}px`;
  menu.style.top = `${top}px`;

  menu.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-menu-index]");
    if (!button) return;
    const item = items[Number(button.dataset.menuIndex)];
    closeMenu();
    item?.onSelect?.();
  });

  openMenu = menu;
  menu.querySelector("button")?.focus();
  return menu;
}

document.addEventListener("click", (event) => {
  if (openMenu && !openMenu.contains(event.target) && !event.target.closest("[data-kebab]")) {
    closeMenu();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeMenu();
});
window.addEventListener("resize", closeMenu);

let openDrawer = null;

export function closeDrawer() {
  if (!openDrawer) return;
  openDrawer.scrim.remove();
  openDrawer.node.remove();
  openDrawer.restoreFocus?.focus?.();
  openDrawer = null;
}

/**
 * Side drawer for short forms. `onSubmit` receives the form's values; returning
 * a rejected promise keeps the drawer open so the error stays visible.
 */
export function showDrawer({ title, description = "", body, submitLabel = "Simpan", onSubmit, wide = false }) {
  closeDrawer();
  const restoreFocus = document.activeElement;

  const scrim = document.createElement("div");
  scrim.className = "aps-scrim aps";
  scrim.addEventListener("click", closeDrawer);

  const node = document.createElement("aside");
  node.className = "aps-drawer aps";
  node.setAttribute("role", "dialog");
  node.setAttribute("aria-modal", "true");
  node.setAttribute("aria-label", title);
  if (wide) node.style.width = "min(620px, 100vw)";
  node.innerHTML = `
    <header class="aps-drawer-head">
      <div style="flex:1 1 auto;min-width:0">
        <h2>${esc(title)}</h2>
        ${description ? `<p>${esc(description)}</p>` : ""}
      </div>
      <button class="aps-iconbtn" data-act="close" type="button" aria-label="Tutup">${icon("close")}</button>
    </header>
    <form class="aps-drawer-body" data-role="drawer-form">${body}</form>
    <footer class="aps-drawer-foot">
      <button class="aps-btn aps-btn--ghost" data-act="close" type="button">Batal</button>
      ${onSubmit ? `<button class="aps-btn" data-act="submit" type="button">${esc(submitLabel)}</button>` : ""}
    </footer>`;

  document.body.append(scrim, node);
  openDrawer = { node, scrim, restoreFocus };

  const form = node.querySelector("[data-role=drawer-form]");
  node.querySelectorAll("[data-act=close]").forEach((button) => button.addEventListener("click", closeDrawer));

  const submit = async () => {
    const button = node.querySelector("[data-act=submit]");
    if (!button || button.disabled) return;
    if (!form.reportValidity()) return;
    button.disabled = true;
    try {
      await onSubmit(Object.fromEntries(new FormData(form).entries()), node);
      closeDrawer();
    } catch (error) {
      button.disabled = false;
      let alert = node.querySelector(".aps-alert");
      if (!alert) {
        alert = document.createElement("div");
        alert.className = "aps-alert";
        alert.setAttribute("role", "alert");
        form.prepend(alert);
      }
      alert.textContent = error?.message ?? "Gagal menyimpan.";
    }
  };

  node.querySelector("[data-act=submit]")?.addEventListener("click", submit);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    submit();
  });
  node.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeDrawer();
  });
  form.querySelector("input, select, textarea")?.focus();
  return node;
}

/** Confirmation dialog. Resolves true only when the user confirms. */
export function confirmDialog({ title, message, confirmLabel = "Lanjutkan", danger = false }) {
  return new Promise((resolve) => {
    const scrim = document.createElement("div");
    scrim.className = "aps-scrim aps";
    const node = document.createElement("div");
    node.className = "aps-dialog aps";
    node.setAttribute("role", "alertdialog");
    node.setAttribute("aria-modal", "true");
    node.innerHTML = `
      <h2>${esc(title)}</h2>
      <p>${esc(message)}</p>
      <div class="aps-dialog-actions">
        <button class="aps-btn aps-btn--ghost" data-act="cancel" type="button">Batal</button>
        <button class="aps-btn${danger ? " aps-btn--danger" : ""}" data-act="ok" type="button">${esc(confirmLabel)}</button>
      </div>`;
    document.body.append(scrim, node);

    const finish = (value) => {
      scrim.remove();
      node.remove();
      document.removeEventListener("keydown", onKey);
      resolve(value);
    };
    const onKey = (event) => {
      if (event.key === "Escape") finish(false);
    };
    scrim.addEventListener("click", () => finish(false));
    node.querySelector("[data-act=cancel]").addEventListener("click", () => finish(false));
    node.querySelector("[data-act=ok]").addEventListener("click", () => finish(true));
    document.addEventListener("keydown", onKey);
    node.querySelector("[data-act=ok]").focus();
  });
}

let toastHost = null;

export function toast(message, tone = "success") {
  if (!toastHost) {
    toastHost = document.createElement("div");
    toastHost.className = "aps-toasts aps";
    document.body.appendChild(toastHost);
  }
  const node = document.createElement("div");
  node.className = `aps-toast aps-toast--${tone}`;
  node.setAttribute("role", "status");
  node.textContent = message;
  toastHost.appendChild(node);
  window.setTimeout(() => node.remove(), 3600);
}
