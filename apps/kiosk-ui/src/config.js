const runtimeConfig = window.__ATTENDANCE_KIOSK_CONFIG__ ?? {};
const urlParams = new URLSearchParams(window.location.search);
const API_BASE_URL_STORAGE_KEY = "attendance.apiBaseUrl";

function defaultApiBaseUrl() {
  const { protocol, hostname, port, origin } = window.location;
  // The dev static server runs on :8080 with the API on :8000. Anywhere else
  // (served straight from the API, or behind a single-origin HTTPS tunnel /
  // reverse proxy) the API shares this page's origin, so use it directly.
  if (port === "8080") {
    return `${protocol}//${hostname}:8000`;
  }
  return origin;
}

function safeStoredApiBaseUrl() {
  try {
    return window.localStorage?.getItem(API_BASE_URL_STORAGE_KEY) ?? null;
  } catch {
    return null;
  }
}

function persistApiBaseUrl(value) {
  if (!value) return;
  try {
    window.localStorage?.setItem(API_BASE_URL_STORAGE_KEY, value);
  } catch {
    // localStorage can be unavailable in restricted browser modes.
  }
}

function normalizeApiBaseUrl(value) {
  if (!value) return null;
  try {
    const parsed = new URL(value, window.location.href);
    return parsed.origin;
  } catch {
    return null;
  }
}

function configuredApiBaseUrl() {
  const queryValue = normalizeApiBaseUrl(urlParams.get("api_base_url") ?? urlParams.get("apiBaseUrl") ?? urlParams.get("api"));
  if (queryValue) {
    persistApiBaseUrl(queryValue);
    return queryValue;
  }
  return normalizeApiBaseUrl(runtimeConfig.apiBaseUrl) ?? normalizeApiBaseUrl(safeStoredApiBaseUrl()) ?? defaultApiBaseUrl();
}

export const kioskConfig = {
  apiBaseUrl: configuredApiBaseUrl(),
  deviceCode: runtimeConfig.deviceCode ?? "web-kiosk-a01",
  previewMirrored: runtimeConfig.previewMirrored ?? true,
  sessionCode: runtimeConfig.sessionCode ?? urlParams.get("session_code") ?? null,
};
