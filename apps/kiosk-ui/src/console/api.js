/* Thin API client for the console.
 *
 * Mirrors the kiosk's contract exactly — cookie session plus the CSRF
 * double-submit header on unsafe methods — so both halves of the app
 * authenticate the same way against the same origin. */

import { kioskConfig } from "../config.js";

// Same origin resolution the kiosk uses, so one tunnel serves both halves.
const API_BASE_URL = kioskConfig.apiBaseUrl;

export class ApiError extends Error {
  constructor(message, { status = 0, body = null, url = "" } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
    this.url = url;
  }
}

function cookie(name) {
  for (const part of document.cookie ? document.cookie.split(";") : []) {
    const trimmed = part.trim();
    if (trimmed.startsWith(`${name}=`)) return decodeURIComponent(trimmed.slice(name.length + 1));
  }
  return "";
}

export function csrfToken() {
  return cookie("csrf_token");
}

function detailOf(body) {
  if (!body) return null;
  if (typeof body === "string") return body;
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.errors) && body.errors.length) return body.errors[0]?.message ?? null;
  if (Array.isArray(body.detail) && body.detail.length) {
    return body.detail[0]?.msg ?? null;
  }
  return null;
}

// Callers register here so a dropped session sends the whole console back to
// login instead of leaving half-loaded pages behind.
let onUnauthorized = () => {};
export function setUnauthorizedHandler(handler) {
  onUnauthorized = typeof handler === "function" ? handler : () => {};
}

async function request(method, path, payload) {
  const url = `${API_BASE_URL}${path}`;
  const upper = method.toUpperCase();
  const headers = {};
  const options = { method: upper, credentials: "include", headers };

  if (!["GET", "HEAD"].includes(upper)) {
    headers["x-csrf-token"] = csrfToken();
  }
  if (payload !== undefined) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(payload);
  }

  let response;
  try {
    response = await fetch(url, options);
  } catch (cause) {
    throw new ApiError("Server tidak dapat dihubungi.", { url });
  }

  const text = await response.text();
  let body = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      // A 403 from CSRF means the session expired; a 403 from a role check does
      // not. Only the former should bounce the user out.
      const message = detailOf(body) ?? "";
      if (response.status === 401 || message.includes("CSRF")) {
        onUnauthorized();
      }
    }
    throw new ApiError(
      detailOf(body) ?? (response.status >= 500 ? "Terjadi kesalahan pada server." : "Permintaan gagal."),
      { status: response.status, body, url },
    );
  }
  return body;
}

export const api = {
  get: (path) => request("GET", path),
  post: (path, payload) => request("POST", path, payload),
  put: (path, payload) => request("PUT", path, payload),
  patch: (path, payload) => request("PATCH", path, payload),
  delete: (path) => request("DELETE", path),
};

export function download(path) {
  // Same-origin download; the session cookie rides along automatically.
  window.open(`${API_BASE_URL}${path}`, "_blank", "noopener");
}

/** Absolute URL for a student's enrolled face photo. */
export function photoUrl(personId) {
  return `${API_BASE_URL}/admin/persons/${encodeURIComponent(personId)}/photo`;
}

export function query(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}
