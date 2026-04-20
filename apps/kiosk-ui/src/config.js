const runtimeConfig = window.__ATTENDANCE_KIOSK_CONFIG__ ?? {};

function defaultApiBaseUrl() {
  const { protocol, hostname } = window.location;
  return `${protocol}//${hostname}:8000`;
}

export const kioskConfig = {
  apiBaseUrl: runtimeConfig.apiBaseUrl ?? defaultApiBaseUrl(),
  deviceCode: runtimeConfig.deviceCode ?? "web-kiosk-a01",
};
