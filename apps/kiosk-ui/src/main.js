import { kioskConfig } from "./config.js";

const API_BASE_URL = kioskConfig.apiBaseUrl;
const DEVICE_CODE = kioskConfig.deviceCode;
const VIDEO_PREVIEW_MIRRORED = Boolean(kioskConfig.previewMirrored);
const ATTENDANCE_SESSION_STORAGE_KEY = "attendanceSessionId";
const CAMERA_STORAGE_KEY = "attendanceSelectedCameraId";
const CAMERA_SELECTION_MODE_KEY = "attendanceCameraSelectionMode";
const AUTO_CAPTURE_INTERVAL_MS = 560;
const AUTO_CAPTURE_TICK_MS = 100;
const ENROLLMENT_FRAME_MIN_INTERVAL_MS = 1200;
const ENROLLMENT_RATE_LIMIT_BACKOFF_MS = 4000;
const STABILITY_WINDOW_MS = 280;
const AFTER_ACCEPT_DELAY_MS = 320;
const MAX_CAPTURE_BACKOFF_MS = 1600;
const ATTENDANCE_SCAN_INTERVAL_MS = 750;
const ATTENDANCE_TICK_MS = 150;
const ATTENDANCE_MAX_BACKOFF_MS = 2200;
const ATTENDANCE_RESULT_PAUSE_MS = 1400;
const ATTENDANCE_SUCCESS_PAUSE_MS = 2600;
const FRAME_CAPTURE_DELAY_MS = 90;
const SESSION_NOT_READY_MESSAGE = "Sesi belum siap. Silakan login ulang.";
const POSE_SEQUENCE = ["front", "left_20", "right_20", "up_or_down"];
const POSE_COPY = {
  front: {
    title: "Hadap Depan",
    shortTitle: "Hadap Depan",
    instruction: "Lihat lurus ke kamera.",
  },
  left_20: {
    title: "Hadap Kiri",
    shortTitle: "Hadap Kiri",
    instruction: "Putar wajah sedikit ke kiri.",
  },
  right_20: {
    title: "Hadap Kanan",
    shortTitle: "Hadap Kanan",
    instruction: "Putar wajah sedikit ke kanan.",
  },
  up_or_down: {
    title: "Gerakkan Dagu",
    shortTitle: "Dagu",
    instruction: "Naikkan atau turunkan dagu sedikit.",
  },
};
const STATUS_COPY = {
  idle: "Siap",
  identity_modal: "Identitas",
  starting: "Memulai",
  searching_face: "Cari Wajah",
  adjusting_position: "Sesuaikan",
  holding: "Tahan",
  capturing: "Merekam",
  pose_complete: "Pose Selesai",
  next_pose: "Pose Berikutnya",
  finishing: "Menyimpan",
  complete: "Selesai",
  error: "Gangguan",
  validating: "Menganalisis",
  accepted: "Berhasil",
  rejected: "Sesuaikan",
  stuck_adjust: "Panduan",
  scanning: "Memindai",
  recognizing: "Mengenali",
  recognized: "Dikenali",
  confirming: "Konfirmasi",
  quality_rejected: "Sesuaikan",
  unknown: "Tidak Dikenal",
  loading_sessions: "Memuat Sesi",
  no_session: "Tanpa Sesi",
  ambiguous: "Mirip",
  session_inactive: "Sesi Tidak Aktif",
  no_matching_session: "Tidak Ada Sesi",
  multiple_matching_sessions: "Sesi Ganda",
  not_in_selected_class: "Bukan Kelas Ini",
  cooldown: "Jeda",
  liveness_check: "Verifikasi",
};
const REASON_COPY = {
  exactly_one_face_required: "Posisikan wajah di dalam oval.",
  too_many_faces: "Pastikan hanya satu wajah di dalam kamera.",
  multiple_faces_detected: "Pastikan hanya satu wajah di dalam kamera.",
  face_too_small: "Dekatkan wajah ke kamera.",
  frame_too_dark: "Cahaya terlalu redup.",
  frame_overexposed: "Cahaya terlalu terang.",
  frame_too_blurry: "Gambar buram, diamkan wajah.",
  frame_low_contrast: "Cari pencahayaan yang lebih merata.",
  face_not_centered: "Posisikan wajah di tengah oval.",
  liveness_below_threshold: "Wajah belum terverifikasi, coba lagi.",
  liveness_failed: "Wajah belum terverifikasi, coba lagi.",
  cooldown: "Tunggu sebentar sebelum mencoba lagi.",
  all_frames_rejected: "Semua frame ditolak, ulangi dengan posisi wajah lebih jelas.",
  no_match_within_threshold: "Wajah tidak dikenali.",
  multi_frame_confirm_failed: "Wajah belum stabil, tahan sebentar.",
  pose_mismatch_front: "Arah wajah belum sesuai.",
  pose_mismatch_left_20: "Putar sedikit lagi ke kiri.",
  pose_mismatch_right_20: "Putar sedikit lagi ke kanan.",
  pose_mismatch_up_or_down: "Naikkan atau turunkan dagu sedikit.",
  accepted: "Wajah berhasil direkam.",
};

const QUALITY_GUIDANCE_COPY = {
  face_too_small: "Dekatkan wajah ke kamera",
  multiple_faces_detected: "Pastikan hanya satu wajah di kamera",
  exactly_one_face_required: "Pastikan satu wajah terlihat jelas",
  frame_too_blurry: "Pastikan wajah tidak bergerak dan kamera fokus",
  face_not_centered: "Posisikan wajah di tengah oval",
  liveness_below_threshold: "Wajah belum terverifikasi, coba lagi",
  liveness_failed: "Wajah belum terverifikasi, coba lagi",
  frame_too_dark: "Cahaya terlalu redup",
  frame_overexposed: "Cahaya terlalu terang",
  frame_low_contrast: "Cari pencahayaan yang lebih merata",
};

const QUALITY_SECONDARY_COPY = {
  face_too_small: "Isi oval dengan wajah lebih besar.",
  multiple_faces_detected: "Kosongkan area kamera dari wajah lain.",
  exactly_one_face_required: "Arahkan wajah sampai terdeteksi di oval.",
  frame_too_blurry: "Tahan posisi wajah sebentar.",
  face_not_centered: "Geser wajah sampai berada di tengah oval.",
  liveness_below_threshold: "Lihat kamera dengan wajah terlihat jelas.",
  liveness_failed: "Lihat kamera dengan wajah terlihat jelas.",
  frame_too_dark: "Pindah ke tempat yang lebih terang.",
  frame_overexposed: "Kurangi cahaya langsung ke wajah.",
  frame_low_contrast: "Cari pencahayaan yang lebih merata.",
};

const QUALITY_REASON_ALIASES = {
  too_many_faces: "multiple_faces_detected",
  liveness_failed: "liveness_below_threshold",
};

function normalizeQualityReason(reason) {
  return QUALITY_REASON_ALIASES[reason] ?? reason ?? null;
}

const elements = {
  app: document.getElementById("app"),
  homeScreen: document.getElementById("home-screen"),
  homeEnrollButton: document.getElementById("home-enroll"),
  homeRecognizeButton: document.getElementById("home-recognize"),
  loginScreen: document.getElementById("login-screen"),
  loginForm: document.getElementById("login-form"),
  loginError: document.getElementById("login-error"),
  loginCancelButton: document.getElementById("login-cancel"),
  adminScreen: document.getElementById("admin-screen"),
  adminTitle: document.getElementById("admin-title"),
  adminEyebrow: document.getElementById("admin-eyebrow"),
  adminBody: document.getElementById("admin-content-body"),
  adminAlert: document.getElementById("admin-alert"),
  adminPrimaryAction: document.getElementById("admin-primary-action"),
  adminModeButton: document.getElementById("mode-admin"),
  adminLogoutButton: document.getElementById("logout-admin"),
  identityModal: document.getElementById("identity-modal"),
  identityCancelButton: document.getElementById("identity-cancel"),
  camera: document.getElementById("camera"),
  cameraStage: document.getElementById("camera-stage"),
  completionScreen: document.getElementById("completion-screen"),
  nextPersonButton: document.getElementById("next-person"),
  status: document.getElementById("status"),
  result: document.getElementById("result"),
  recognitionResult: document.getElementById("recognition-result"),
  faceOval: document.getElementById("face-oval"),
  ovalProgress: document.getElementById("oval-progress"),
  ovalPrimary: document.getElementById("oval-primary"),
  ovalSecondary: document.getElementById("oval-secondary"),
  successBurst: document.getElementById("success-burst"),
  cancelButton: document.getElementById("cancel-enrollment"),
  attendanceResultCard: document.getElementById("attendance-result-card"),
  attendancePhoto: document.getElementById("attendance-photo"),
  attendanceAvatar: document.getElementById("attendance-avatar"),
  attendanceCardTitle: document.getElementById("attendance-card-title"),
  attendanceName: document.getElementById("attendance-name"),
  attendanceStudent: document.getElementById("attendance-student"),
  attendanceConfidence: document.getElementById("attendance-confidence"),
  attendanceDate: document.getElementById("attendance-date"),
  attendanceTime: document.getElementById("attendance-time"),
  attendanceSession: document.getElementById("attendance-session"),
  attendanceMessage: document.getElementById("attendance-message"),
  attendanceCooldown: document.getElementById("attendance-cooldown"),
  attendanceSessionCopy: document.getElementById("attendance-session-copy"),
  attendanceSessionPicker: document.getElementById("attendance-session-picker"),
  attendanceSessionSelect: document.getElementById("attendance-session-select"),
  attendanceConfirmModal: document.getElementById("attendance-confirm-modal"),
  attendanceConfirmStatus: document.getElementById("attendance-confirm-status"),
  attendanceConfirmPhoto: document.getElementById("attendance-confirm-photo"),
  attendanceConfirmAvatar: document.getElementById("attendance-confirm-avatar"),
  attendanceConfirmMessage: document.getElementById("attendance-confirm-message"),
  attendanceConfirmAccept: document.getElementById("attendance-confirm-accept"),
  attendanceConfirmRetry: document.getElementById("attendance-confirm-retry"),
  attendanceConfirmCancel: document.getElementById("attendance-confirm-cancel"),
  confirmName: document.getElementById("confirm-name"),
  confirmStudentId: document.getElementById("confirm-student-id"),
  confirmEmail: document.getElementById("confirm-email"),
  confirmClass: document.getElementById("confirm-class"),
  confirmLecturer: document.getElementById("confirm-lecturer"),
  confirmSession: document.getElementById("confirm-session"),
  confirmSessionCode: document.getElementById("confirm-session-code"),
  confirmDate: document.getElementById("confirm-date"),
  confirmTime: document.getElementById("confirm-time"),
  confirmConfidence: document.getElementById("confirm-confidence"),
  attendanceSuccessLog: document.getElementById("attendance-success-log"),
  attendanceSuccessList: document.getElementById("attendance-success-list"),
  attendanceSuccessEmpty: document.getElementById("attendance-success-empty"),
  startForm: document.getElementById("enrollment-form"),
  startButton: document.getElementById("start-enrollment"),
  identityClassSelect: document.getElementById("identity-class"),
  challengeOverlay: document.getElementById("challenge-overlay"),
  challengeSwatch: document.getElementById("challenge-swatch"),
  challengeText: document.getElementById("challenge-text"),
  challengeCountdown: document.getElementById("challenge-countdown"),
  autoStatus: document.getElementById("auto-status"),
  recognitionButton: document.getElementById("capture-recognition"),
  enrollModeButton: document.getElementById("mode-enroll"),
  recognizeModeButton: document.getElementById("mode-recognize"),
  enrollmentPanel: document.getElementById("enrollment-panel"),
  recognitionPanel: document.getElementById("recognition-panel"),
  arrows: {
    left: document.getElementById("arrow-left"),
    right: document.getElementById("arrow-right"),
    up: document.getElementById("arrow-up"),
    down: document.getElementById("arrow-down"),
  },
  metrics: {
    brightness: document.getElementById("metric-brightness"),
    blur: document.getElementById("metric-blur"),
    contrast: document.getElementById("metric-contrast"),
    overexposed: document.getElementById("metric-overexposed"),
    underexposed: document.getElementById("metric-underexposed"),
    centering: document.getElementById("metric-centering"),
    pose: document.getElementById("metric-pose"),
    liveness: document.getElementById("metric-liveness"),
  },
  enrollTopBar: document.getElementById("enroll-top-bar"),
  enrollStatusDot: document.getElementById("enroll-status-dot"),
  enrollStudentName: document.getElementById("enroll-student-name"),
  enrollInstruction: document.getElementById("enroll-instruction"),
  poseDots: document.getElementById("pose-dots"),
  enrollBottomSheet: document.getElementById("enroll-bottom-sheet"),
  enrollWarning: document.getElementById("enroll-warning"),
  enrollCountdown: document.getElementById("enroll-countdown"),
  captureButton: document.getElementById("capture-pose"),
  finishButton: document.getElementById("finish-enrollment"),
  attendanceTopBar: document.getElementById("attendance-top-bar"),
  attendanceSessionBadge: document.getElementById("attendance-session-badge"),
  attendanceChangeSessionBtn: document.getElementById("attendance-change-session-btn"),
  attendanceCloseBtn: document.getElementById("attendance-close-btn"),
  attendanceToast: document.getElementById("attendance-toast"),
  attendanceToastIcon: document.getElementById("attendance-toast-icon"),
  attendanceToastText: document.getElementById("attendance-toast-text"),
  attendanceEdgeSheet: document.getElementById("attendance-edge-sheet"),
  attendanceEdgeTitle: document.getElementById("attendance-edge-title"),
  attendanceEdgeMessage: document.getElementById("attendance-edge-message"),
  attendanceEdgeActions: document.getElementById("attendance-edge-actions"),
};

const state = {
  mode: "enroll",
  screen: "home",
  cameraReady: false,
  cameraRecovering: false,
  enrollmentState: "idle",
  enrollmentSessionId: null,
  personId: null,
  requiredPoses: [...POSE_SEQUENCE],
  acceptedPerPose: 0,
  remainingPerPose: Object.fromEntries(POSE_SEQUENCE.map((pose) => [pose, 0])),
  nextPose: "front",
  displayPose: null,
  progressPercent: 0,
  captureStatus: "idle",
  uiHint: "Ikuti panduan di layar.",
  lastFrameResponse: null,
  lastRequestAt: 0,
  lastEnrollmentFrameAt: 0,
  enrollmentBackoffUntil: 0,
  dynamicCaptureDelay: AUTO_CAPTURE_INTERVAL_MS,
  requestInFlight: false,
  enrollmentFrameInFlight: false,
  captureLoopId: null,
  transitionTimerId: null,
  stableSince: null,
  autoFinishStarted: false,
  consecutiveCaptureErrors: 0,
  lastError: null,
  attendanceStatus: "idle",
  attendanceSessionCode: String(kioskConfig.sessionCode ?? "").trim() || null,
  attendanceLoopId: null,
  attendanceRequestInFlight: false,
  attendanceLastRequestAt: 0,
  attendanceDynamicDelay: ATTENDANCE_SCAN_INTERVAL_MS,
  attendancePausedUntil: 0,
  attendanceCooldownUntil: 0,
  attendanceLastResponse: null,
  attendanceThumbnail: null,
  attendanceConsecutiveErrors: 0,
  attendanceSessionLookupInFlight: false,
  attendanceSessionLookupDone: false,
  attendanceSessionNotice: "",
  attendanceSessionLoadError: "",
  availableAttendanceClasses: [],
  attendanceClassLookupInFlight: false,
  attendanceClassLoadError: "",
  attendanceClassesFailed404: false,
  attendanceClassesLoadedAt: 0,
  availableAttendanceSessions: [],
  selectedAttendanceSessionId: null,
  selectedAttendanceClassId: null,
  pendingAttendance: null,
  attendanceConfirmInFlight: false,
  successfulAttendances: [],
  adminUser: null,
  pendingModeAfterLogin: "recognize",
  adminView: "dashboard",
  adminData: {},
  adminEdit: null,
  adminSessionFilters: {
    class_id: "",
    date: "",
    status: "",
    include_deleted: false,
  },
  cameraDevices: [],
  selectedCameraId: readStoredCameraId(),
  cameraSelectionMode: readStoredCameraSelectionMode(),
  cameraStatus: "checking",
  cameraWarning: "",
  livenessChallengeId: null,
  livenessChallengeColor: null,
  livenessChallengeLabel: "",
  livenessChallengeExpiresAt: 0,
  livenessChallengeActive: false,
  livenessChallengeTimerId: null,
  livenessChallengeAttempts: 0,
};

let frameCanvas = null;
let attendanceSessionLookupPromise = null;

function readStoredCameraId() {
  try {
    if (readStoredCameraSelectionMode() !== "manual") {
      window.localStorage.removeItem(CAMERA_STORAGE_KEY);
      return "";
    }
    return window.localStorage.getItem(CAMERA_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

function readStoredCameraSelectionMode() {
  try {
    return window.localStorage.getItem(CAMERA_SELECTION_MODE_KEY) === "manual" ? "manual" : "auto";
  } catch {
    return "auto";
  }
}

function storeCameraId(deviceId, { manual = false } = {}) {
  state.selectedCameraId = deviceId || "";
  state.cameraSelectionMode = manual && state.selectedCameraId ? "manual" : "auto";
  try {
    if (state.cameraSelectionMode === "manual") {
      window.localStorage.setItem(CAMERA_STORAGE_KEY, state.selectedCameraId);
      window.localStorage.setItem(CAMERA_SELECTION_MODE_KEY, "manual");
    } else {
      window.localStorage.removeItem(CAMERA_STORAGE_KEY);
      window.localStorage.removeItem(CAMERA_SELECTION_MODE_KEY);
    }
  } catch {
    // localStorage can be unavailable in private or embedded contexts.
  }
}

function rememberActiveCameraId(deviceId) {
  state.selectedCameraId = deviceId || "";
}

function cameraLabel(device, index) {
  return device.label || `Kamera ${index + 1}`;
}

function cameraNameLooksBack(label = "") {
  return /\b(back|rear|environment|world|belakang)\b/i.test(label);
}

function cameraNameLooksFront(label = "") {
  return /\b(front|user|face|depan|webcam)\b/i.test(label);
}

function cameraTrackLooksBack(track) {
  const settings = track?.getSettings?.() ?? {};
  return settings.facingMode === "environment" || cameraNameLooksBack(track?.label ?? "");
}

function stopMediaStream(stream) {
  if (stream?.getTracks) {
    stream.getTracks().forEach((track) => track.stop());
  }
}

function mediaErrorName(error) {
  return error?.name || error?.cause?.name || "";
}

function sourceMediaError(error) {
  return error?.cause ?? error;
}

function cameraWarningFor(error) {
  if (!window.isSecureContext) {
    return "Browser memblokir kamera karena halaman tidak aman. Buka kiosk dari http://localhost:8080 atau HTTPS.";
  }
  const name = mediaErrorName(sourceMediaError(error));
  if (name === "NotAllowedError" || name === "PermissionDeniedError" || name === "SecurityError") {
    return "Izin kamera ditolak. Izinkan kamera untuk localhost:8080 di browser.";
  }
  if (name === "NotFoundError" || name === "DevicesNotFoundError") {
    return "Kamera tidak ditemukan. Sambungkan atau aktifkan kamera, lalu muat ulang.";
  }
  if (name === "NotReadableError" || name === "TrackStartError" || name === "AbortError") {
    return "Kamera ditemukan tetapi tidak bisa dimulai. Tutup aplikasi atau tab lain yang memakai kamera, lalu muat ulang.";
  }
  if (name === "OverconstrainedError" || name === "ConstraintNotSatisfiedError") {
    return "Pilihan kamera tidak tersedia. Pilih kamera default atau periksa koneksi kamera.";
  }
  if (name === "WrongFacingModeError") {
    return "Kamera yang aktif adalah kamera belakang. Aktifkan kamera depan atau pilih kamera depan di Admin.";
  }
  if (name === "NotSupportedError") {
    return "Browser tidak mendukung akses kamera untuk halaman ini.";
  }
  return "Kamera tidak dapat dimulai. Periksa izin browser dan koneksi kamera.";
}

function shouldTryNextCamera(error) {
  const name = mediaErrorName(sourceMediaError(error));
  if (name === "NotAllowedError" || name === "PermissionDeniedError" || name === "SecurityError") {
    return false;
  }
  return true;
}

function cameraStartupError(error, failures) {
  const source = sourceMediaError(error);
  const wrapped = new Error(cameraWarningFor(source));
  wrapped.name = mediaErrorName(source) || "CameraError";
  wrapped.cause = source;
  wrapped.cameraFailures = failures;
  return wrapped;
}

function cameraErrorDetails(error) {
  const source = sourceMediaError(error);
  return {
    error: String(source ?? error),
    name: mediaErrorName(source),
    message: source?.message ?? error?.message ?? "",
    warning: cameraWarningFor(error),
    cameras_detected: state.cameraDevices.length,
    selected_camera_id: state.selectedCameraId || null,
    attempts: (error?.cameraFailures ?? []).map((failure) => ({
      camera: failure.label,
      error: String(failure.error),
      name: mediaErrorName(failure.error),
      message: failure.error?.message ?? "",
    })),
  };
}

const ENROLLMENT_STATES = new Set([
  "idle",
  "identity_modal",
  "starting",
  "searching_face",
  "adjusting_position",
  "holding",
  "capturing",
  "pose_complete",
  "next_pose",
  "liveness_check",
  "finishing",
  "complete",
  "error",
]);

function setEnrollmentState(nextState, patch = {}) {
  if (!ENROLLMENT_STATES.has(nextState)) {
    throw new Error(`Unknown enrollment state: ${nextState}`);
  }
  Object.assign(state, patch);
  state.enrollmentState = nextState;
  elements.app.dataset.enrollmentState = nextState;
}

function setScreen(screen) {
  state.screen = screen;
  elements.app.dataset.screen = screen;
  document.documentElement.dataset.screen = screen;
  document.body.dataset.screen = screen;
  elements.homeScreen.classList.toggle("is-hidden", screen !== "home");
  elements.loginScreen.classList.toggle("is-hidden", screen !== "login");
  elements.adminScreen.classList.toggle("is-hidden", screen !== "admin");
  elements.enrollmentPanel.classList.toggle("is-hidden", screen !== "capture" && screen !== "recognize" && screen !== "complete");
  elements.cameraStage.classList.toggle("is-hidden", screen === "complete" || screen === "admin" || screen === "login");
  elements.completionScreen.classList.toggle("is-hidden", screen !== "complete");
  elements.recognitionPanel.classList.toggle("is-hidden", screen !== "recognize");
}

function showIdentityModal() {
  setEnrollmentState("identity_modal");
  populateIdentityClassOptions();
  elements.identityModal.classList.remove("is-hidden");
  const studentIdInput = document.getElementById("student-id");
  if (studentIdInput && !studentIdInput.value.trim()) {
    studentIdInput.value = generatedStudentId();
    prefillEnrollmentStudentId(studentIdInput);
  }
  window.setTimeout(() => studentIdInput?.focus(), 0);
}

function populateIdentityClassOptions(selected = "") {
  if (!elements.identityClassSelect) return;
  const classes = state.adminData.classes ?? [];
  elements.identityClassSelect.innerHTML = `<option value="">Pilih kelas</option>${classes
    .filter((item) => item.is_active !== false)
    .map((item) => `<option value="${item.class_id}" ${item.class_id === selected ? "selected" : ""}>${escapeHtml(item.class_code)} - ${escapeHtml(item.class_name)}</option>`)
    .join("")}`;
}

async function prefillEnrollmentStudentId(input) {
  try {
    const response = await getJson("/admin/ids/next?entity=student");
    if (input && !input.dataset.userEdited && input.value.startsWith("AUTO-") && response?.id) {
      input.value = response.id;
    }
  } catch (error) {
    console.debug("Tidak dapat mengambil ID otomatis dari backend", error);
  }
}

function closeIdentityModal() {
  elements.identityModal.classList.add("is-hidden");
  if (!state.enrollmentSessionId && state.enrollmentState === "identity_modal") {
    setEnrollmentState("idle");
  }
}

function showHomeScreen() {
  // Neutral landing that starts no scanning loop — used on reload when an
  // admin is already logged in, so they pick an action instead of the kiosk
  // silently entering attendance mode.
  state.mode = "recognize";
  stopAttendanceLoop();
  stopAutoCaptureLoop();
  elements.enrollModeButton.classList.remove("is-active");
  elements.recognizeModeButton.classList.remove("is-active");
  elements.adminModeButton.classList.remove("is-active");
  setScreen("home");
  renderWizard();
}

async function ensureCameraReady() {
  // Re-acquire the camera if the stream was dropped (common on Android when
  // the video element was hidden during admin/complete screens). Without this,
  // starting a new enrollment leaves the capture loop running against a dead
  // stream and nothing happens until a manual page reload.
  const stream = elements.camera?.srcObject;
  const liveTrack = stream?.getVideoTracks?.().some((track) => track.readyState === "live");
  if (state.cameraReady && liveTrack) {
    return true;
  }
  await startCamera();
  return state.cameraReady;
}

function setMode(mode) {
  if (mode === "admin") {
    openAdmin();
    return;
  }
  if (mode === "enroll" && !authSessionReady()) {
    state.pendingModeAfterLogin = mode;
    handleAuthRequired(SESSION_NOT_READY_MESSAGE, { intendedMode: mode });
    return;
  }
  state.mode = mode;
  const enrollActive = mode === "enroll";
  elements.enrollModeButton.classList.toggle("is-active", enrollActive);
  elements.recognizeModeButton.classList.toggle("is-active", !enrollActive);
  elements.adminModeButton.classList.remove("is-active");
  elements.enrollmentPanel.classList.toggle("recognition-active", !enrollActive);
  if (!enrollActive) {
    stopAutoCaptureLoop();
    startAttendanceMode();
  } else if (state.enrollmentSessionId && !isTerminalEnrollmentState()) {
    stopAttendanceLoop();
    setScreen("capture");
    startAutoCaptureLoop();
  } else if (state.enrollmentState === "complete") {
    stopAttendanceLoop();
    setScreen("complete");
  } else {
    stopAttendanceLoop();
    setScreen("home");
  }
  renderWizard();
}

function generatedStudentId() {
  const now = new Date();
  const date = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}`;
  const time = `${String(now.getHours()).padStart(2, "0")}${String(now.getMinutes()).padStart(2, "0")}${String(now.getSeconds()).padStart(2, "0")}`;
  return `AUTO-${date}-${time}`;
}

function normalizeSessionCode(value) {
  const sessionCode = String(value ?? "").trim();
  return sessionCode.length > 0 ? sessionCode : null;
}

function rememberSession(session) {
  if (!session?.session_id) {
    return;
  }
  state.selectedAttendanceSessionId = session.session_id;
  state.selectedAttendanceClassId = session.class_id ?? null;
  state.attendanceSessionCode = session.session_code ?? null;
  try {
    window.localStorage.setItem(ATTENDANCE_SESSION_STORAGE_KEY, session.session_id);
  } catch (error) {
    console.debug("Unable to persist attendance session id", error);
  }
}

function forgetSessionCode({ notice = "" } = {}) {
  state.selectedAttendanceSessionId = null;
  state.selectedAttendanceClassId = null;
  state.attendanceSessionCode = null;
  if (notice) {
    state.attendanceSessionNotice = notice;
  }
  try {
    window.localStorage.removeItem(ATTENDANCE_SESSION_STORAGE_KEY);
  } catch (error) {
    console.debug("Unable to clear attendance session id", error);
  }
}

function sessionTimestamp(value) {
  if (!value) {
    return null;
  }
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
}

function sessionIsCurrentlyUsable(session) {
  if (!session?.is_active) {
    return false;
  }
  if (session.repeat_days && session.repeat_days.length > 0 && session.start_time) {
    const witaNow = new Date(Date.now() + 8 * 60 * 60 * 1000);
    const dayNames = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
    const todayWita = dayNames[witaNow.getUTCDay()];
    if (!session.repeat_days.includes(todayWita)) {
      return false;
    }
    const nowMinutes = witaNow.getUTCHours() * 60 + witaNow.getUTCMinutes();
    const startMinutes = parseTimeToMinutes(session.start_time);
    const endMinutes = parseTimeToMinutes(session.end_time);
    if (startMinutes !== null && nowMinutes < startMinutes) {
      return false;
    }
    if (endMinutes !== null && nowMinutes > endMinutes) {
      return false;
    }
    return true;
  }
  const startsAt = sessionTimestamp(session.starts_at);
  const endsAt = sessionTimestamp(session.ends_at);
  if (startsAt !== null && startsAt > Date.now()) {
    return false;
  }
  if (endsAt !== null && endsAt < Date.now()) {
    return false;
  }
  return true;
}

function parseTimeToMinutes(value) {
  if (!value) return null;
  const match = String(value).match(/^(\d{1,2}):(\d{2})/);
  if (!match) return null;
  return parseInt(match[1], 10) * 60 + parseInt(match[2], 10);
}

function attendanceSessionItems(response) {
  if (Array.isArray(response)) {
    return response;
  }
  if (Array.isArray(response?.items)) {
    return response.items;
  }
  return [];
}

function selectedAttendanceSession() {
  if (!state.selectedAttendanceSessionId) {
    return null;
  }
  return state.availableAttendanceSessions.find((session) => session.session_id === state.selectedAttendanceSessionId && sessionIsCurrentlyUsable(session)) ?? null;
}

function selectedAttendanceSessionCode() {
  return selectedAttendanceSession()?.session_code ?? null;
}

function attendanceSessionLabel(session, { includeClass = true } = {}) {
  if (!session) {
    return "";
  }
  const name = session.session_name || "Sesi absensi";
  const code = session.session_code ? ` (${session.session_code})` : "";
  const classLabel = includeClass ? session.class_name || session.class_code || "" : "";
  return classLabel ? `${name} - ${classLabel}${code}` : `${name}${code}`;
}

function resolvedSessionLabel(session, { includeCode = false } = {}) {
  if (!session) return "-";
  const code = includeCode && session.session_code ? ` (${session.session_code})` : "";
  return `${session.session_name || "Sesi absensi"}${code}`;
}

function resolvedSessionStart(session) {
  return session?.start_time ?? session?.starts_at ?? null;
}

function resolvedSessionEnd(session) {
  return session?.end_time ?? session?.ends_at ?? null;
}

function resetAttendanceSessionLookup() {
  state.attendanceSessionLookupInFlight = false;
  state.attendanceSessionLookupDone = false;
  state.attendanceSessionLoadError = "";
  state.availableAttendanceSessions = [];
  attendanceSessionLookupPromise = null;
}

async function loadAttendanceClasses() {
  if (state.attendanceClassLookupInFlight) return;
  if (state.attendanceClassesFailed404) return;
  if (state.attendanceClassesLoadedAt > 0 && Date.now() - state.attendanceClassesLoadedAt < 30000) return;
  state.attendanceClassLookupInFlight = true;
  state.attendanceClassLoadError = "";
  try {
    const classes = await getJson("/attendance/classes/active");
    state.availableAttendanceClasses = Array.isArray(classes) ? classes : [];
    state.attendanceClassesLoadedAt = Date.now();
    state.attendanceClassesFailed404 = false;
    // Skip the "Pilih Kelas" step when there is exactly one active class —
    // the operator shouldn't have to pick from a list of one.
    if (
      !state.selectedAttendanceClassId &&
      !state.selectedAttendanceSessionId &&
      state.availableAttendanceClasses.length === 1
    ) {
      const onlyClass = state.availableAttendanceClasses[0];
      if (onlyClass?.class_id) {
        state.selectedAttendanceClassId = onlyClass.class_id;
        state.attendanceSessionLookupDone = false;
        await loadSessionsForClass(onlyClass.class_id);
      }
    }
  } catch (error) {
    console.warn("Tidak dapat memuat kelas absensi aktif", error);
    state.availableAttendanceClasses = [];
    if (error?.status === 404) {
      state.attendanceClassLoadError = "Endpoint kelas absensi belum tersedia.";
      state.attendanceClassesFailed404 = true;
    } else {
      state.attendanceClassLoadError = "Kelas absensi tidak dapat dimuat.";
    }
  } finally {
    state.attendanceClassLookupInFlight = false;
    if (state.mode === "recognize") {
      renderAttendance();
    }
  }
}

async function loadSessionsForClass(classId) {
  state.attendanceSessionLookupInFlight = true;
  state.attendanceSessionLoadError = "";
  try {
    const sessions = await getJson(`/attendance/classes/${classId}/sessions/active`);
    const usableSessions = attendanceSessionItems(sessions).filter(sessionIsCurrentlyUsable);
    state.availableAttendanceSessions = usableSessions;
    // Auto-select when the chosen class has exactly one usable session, so
    // scanning starts immediately instead of forcing a second manual pick.
    if (!state.selectedAttendanceSessionId && usableSessions.length === 1) {
      rememberSession(usableSessions[0]);
      if (state.selectedAttendanceSessionId && state.mode === "recognize") {
        state.attendanceStatus = "scanning";
        state.attendanceLastResponse = null;
        startAttendanceLoop();
      }
    }
  } catch (error) {
    console.warn("Tidak dapat memuat sesi untuk kelas", error);
    state.availableAttendanceSessions = [];
    state.attendanceSessionLoadError = "Sesi absensi tidak dapat dimuat.";
  } finally {
    state.attendanceSessionLookupInFlight = false;
    state.attendanceSessionLookupDone = true;
    if (state.mode === "recognize") {
      renderAttendance();
    }
  }
}

async function refreshAttendanceSessionCode({ force = false, staleMessage = "Sesi lama sudah tidak aktif. Silakan pilih sesi baru." } = {}) {
  if (attendanceSessionLookupPromise) {
    return attendanceSessionLookupPromise;
  }
  if (!force && state.attendanceSessionLookupDone) {
    return selectedAttendanceSessionCode();
  }

  state.attendanceSessionLookupInFlight = true;
  state.attendanceSessionLoadError = "";
  attendanceSessionLookupPromise = (async () => {
    try {
      const response = await getJson("/attendance/sessions/active");
      const usableSessions = attendanceSessionItems(response).filter(sessionIsCurrentlyUsable);
      const storedSessionId = (() => {
        try {
          return window.localStorage.getItem(ATTENDANCE_SESSION_STORAGE_KEY) || null;
        } catch {
          return null;
        }
      })();
      state.availableAttendanceSessions = usableSessions;

      if (storedSessionId) {
        const stillActive = usableSessions.some((item) => item.session_id === storedSessionId);
        if (!stillActive) {
          forgetSessionCode({ notice: staleMessage });
        } else {
          const restored = usableSessions.find((item) => item.session_id === storedSessionId);
          if (restored) {
            rememberSession(restored);
          }
        }
      }
    } catch (error) {
      console.warn("Tidak dapat memuat sesi absensi aktif", error);
      state.availableAttendanceSessions = [];
      state.attendanceSessionLoadError = "Sesi absensi tidak dapat dimuat.";
      if (!state.attendanceSessionLookupDone && state.selectedAttendanceSessionId) {
        forgetSessionCode();
      }
    } finally {
      state.attendanceSessionLookupInFlight = false;
      state.attendanceSessionLookupDone = true;
      attendanceSessionLookupPromise = null;
      if (state.mode === "recognize") {
        renderAttendance();
      }
    }
    return selectedAttendanceSessionCode();
  })();

  return attendanceSessionLookupPromise;
}

function poseTitle(pose) {
  return POSE_COPY[pose]?.shortTitle ?? pose;
}

function poseInstruction(pose) {
  return userFacingInstructionText(POSE_COPY[pose]?.instruction ?? "Ikuti panduan.");
}

function currentPose() {
  return state.displayPose ?? state.nextPose ?? POSE_SEQUENCE.find((pose) => (state.remainingPerPose[pose] ?? 0) > 0) ?? null;
}

function poseProgress(pose) {
  const remaining = state.remainingPerPose[pose] ?? state.acceptedPerPose;
  const accepted = Math.max(state.acceptedPerPose - remaining, 0);
  return { accepted, remaining, complete: state.acceptedPerPose > 0 && remaining === 0 };
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function faceWidthRatio(quality = null) {
  if (!quality || !quality.face_width_px) {
    return null;
  }
  const videoWidth = elements.camera.videoWidth || 640;
  return videoWidth > 0 ? quality.face_width_px / videoWidth : null;
}

function distanceState(response) {
  const ratio = faceWidthRatio(response?.quality);
  if (ratio === null) {
    return { key: "unknown", label: "Cari wajah" };
  }
  if (ratio < 0.28) {
    return { key: "too_far", label: "Dekatkan wajah" };
  }
  if (ratio > 0.58) {
    return { key: "too_close", label: "Jauhkan wajah sedikit" };
  }
  if (ratio >= 0.34 && ratio <= 0.5) {
    return { key: "ideal", label: "Jarak sudah pas" };
  }
  return { key: "ok", label: "Jarak cukup baik" };
}

function speedModeLabel() {
  if (!state.acceptedPerPose) {
    return "Mode perekaman";
  }
  if (state.acceptedPerPose <= 2) {
    return `Mode cepat - ${state.acceptedPerPose}/pose`;
  }
  if (state.acceptedPerPose === 3) {
    return `Mode normal - ${state.acceptedPerPose}/pose`;
  }
  return `Mode ketat - ${state.acceptedPerPose}/pose`;
}

function allPosesComplete() {
  return state.requiredPoses.length > 0 && state.requiredPoses.every((pose) => (state.remainingPerPose[pose] ?? 0) === 0);
}

function isTerminalEnrollmentState() {
  return state.enrollmentState === "complete" || state.enrollmentState === "error" || state.enrollmentState === "idle";
}

let previousActivePose = null;

function renderPoseDots() {
  const nextActive = currentPose();
  const poseChanged = nextActive !== previousActivePose && previousActivePose !== null;
  if (!elements.poseDots) return;
  elements.poseDots.innerHTML = "";
  for (const pose of state.requiredPoses) {
    const progress = poseProgress(pose);
    const active = pose === nextActive && !progress.complete;
    const dot = document.createElement("span");
    dot.className = `pose-dot${active ? " active" : ""}${progress.complete ? " complete" : ""}`;
    dot.setAttribute("aria-label", `${poseTitle(pose)}: ${progress.complete ? "selesai" : active ? "aktif" : "menunggu"}`);
    elements.poseDots.appendChild(dot);
  }
  previousActivePose = nextActive;
}

function setOverlay(text, tone = "idle") {
  // Overlay removed from enrollment — instruction shown via enroll-instruction
  // Kept for backward compatibility with attendance mode
}

function setStatusBadge(status) {
  if (elements.enrollStatusDot) {
    elements.enrollStatusDot.className = `enroll-status-dot ${status}`;
  }
  if (state.mode === "recognize") {
    elements.autoStatus.textContent = STATUS_COPY[state.attendanceStatus] ?? "Mode Absensi";
    elements.autoStatus.className = `status-pill ${state.attendanceStatus}`;
    return;
  }
  elements.autoStatus.textContent =
    !state.enrollmentSessionId && state.cameraReady ? "Kamera siap" : (STATUS_COPY[state.enrollmentState] ?? state.enrollmentState);
  elements.autoStatus.className = `status-pill ${state.enrollmentState}`;
}

function updateCountdown(msRemaining = null) {
  if (msRemaining === null || msRemaining <= 0) {
    if (elements.enrollCountdown) elements.enrollCountdown.textContent = "";
    elements.faceOval.style.setProperty("--hold-progress", "0");
    elements.faceOval.style.setProperty("--hold-angle", "0deg");
    return;
  }
  const progress = clamp(1 - msRemaining / STABILITY_WINDOW_MS, 0, 1);
  elements.faceOval.style.setProperty("--hold-progress", progress.toFixed(3));
  elements.faceOval.style.setProperty("--hold-angle", `${Math.round(progress * 360)}deg`);
  const step = Math.max(1, Math.ceil(msRemaining / (STABILITY_WINDOW_MS / 3)));
  if (elements.enrollCountdown) {
    elements.enrollCountdown.textContent = `Tahan... ${step}`;
  }
}

function updateMetrics(quality = null) {
  const fallback = "-";
  elements.metrics.brightness.textContent = quality ? quality.brightness_score.toFixed(1) : fallback;
  elements.metrics.blur.textContent = quality ? quality.blur_score.toFixed(1) : fallback;
  elements.metrics.contrast.textContent = quality ? quality.contrast_score.toFixed(1) : fallback;
  elements.metrics.overexposed.textContent = quality ? `${(quality.overexposed_ratio * 100).toFixed(1)}%` : fallback;
  elements.metrics.underexposed.textContent = quality ? `${(quality.underexposed_ratio * 100).toFixed(1)}%` : fallback;
  elements.metrics.centering.textContent = quality
    ? `${quality.face_center_offset_x.toFixed(2)} / ${quality.face_center_offset_y.toFixed(2)}`
    : fallback;
  elements.metrics.pose.textContent = quality
    ? `${quality.pose_yaw.toFixed(1)} / ${quality.pose_pitch.toFixed(1)}`
    : fallback;
  elements.metrics.liveness.textContent = quality ? quality.liveness_score.toFixed(2) : fallback;
}

function clearArrows() {
  for (const arrow of Object.values(elements.arrows)) {
    arrow.classList.remove("is-active", "is-move", "is-turn", "is-chin");
    arrow.removeAttribute("data-arrow-kind");
  }
}

function activateArrow(arrowConfig) {
  clearArrows();
  if (!arrowConfig) {
    return;
  }
  const direction = typeof arrowConfig === "string" ? arrowConfig : arrowConfig.direction;
  const kind = typeof arrowConfig === "string" ? "move" : arrowConfig.kind ?? "move";
  if (direction && elements.arrows[direction]) {
    elements.arrows[direction].classList.add("is-active", `is-${kind}`);
    elements.arrows[direction].dataset.arrowKind = kind;
  }
}

function getUserFacingDirection(rawDirection, isPreviewMirrored = VIDEO_PREVIEW_MIRRORED) {
  // Backend yaw/offset values are measured on the raw camera frame. The video
  // preview may be mirrored for a selfie feel, so only user-facing arrows and
  // movement text swap left/right. Requests sent to the backend stay unchanged.
  if (!isPreviewMirrored || (rawDirection !== "left" && rawDirection !== "right")) {
    return rawDirection;
  }
  return rawDirection === "left" ? "right" : "left";
}

function userFacingInstructionText(text) {
  if (!VIDEO_PREVIEW_MIRRORED || !text) {
    return text;
  }
  return String(text)
    .replaceAll("ke kiri", "__DIR_RIGHT__")
    .replaceAll("ke kanan", "ke kiri")
    .replaceAll("__DIR_RIGHT__", "ke kanan");
}

function arrowDescriptor(direction, kind = "move") {
  return direction ? { direction, kind } : null;
}

function arrowFromGuidanceDirection(guidanceDirection) {
  const directionMap = {
    move_left: { direction: "left", kind: "move" },
    move_right: { direction: "right", kind: "move" },
    turn_left: { direction: "left", kind: "turn" },
    turn_right: { direction: "right", kind: "turn" },
    move_up: { direction: "up", kind: "move" },
    move_down: { direction: "down", kind: "move" },
    raise_chin: { direction: "up", kind: "chin" },
    lower_chin: { direction: "down", kind: "chin" },
    raise_or_lower_chin: { direction: "up", kind: "chin" },
  };
  const arrow = directionMap[guidanceDirection] ?? null;
  if (!arrow) {
    return null;
  }
  return arrowDescriptor(getUserFacingDirection(arrow.direction), arrow.kind);
}

function horizontalDirection(offsetX) {
  if (Math.abs(offsetX) < 0.12) {
    return null;
  }

  // Backend offsets are camera-space values from the unmirrored captured
  // frame. The preview can be mirrored like a selfie camera, so UI arrows and
  // movement text swap left/right while backend pose values stay unchanged.
  const rawDirection = offsetX > 0 ? "left" : "right";
  return getUserFacingDirection(rawDirection);
}

function verticalDirection(offsetY) {
  if (Math.abs(offsetY) < 0.12) {
    return null;
  }
  return offsetY > 0 ? "up" : "down";
}

function movementInstruction(direction) {
  const copy = {
    left: "Geser wajah sedikit ke kiri",
    right: "Geser wajah sedikit ke kanan",
    up: "Naikkan wajah sedikit",
    down: "Turunkan wajah sedikit",
  };
  return copy[direction] ?? "Posisikan wajah di tengah";
}

function localizedHint(response) {
  if (!response) {
    return "Ikuti panduan di layar.";
  }
  if (response.accepted) {
    return "Wajah berhasil direkam.";
  }
  if (response.capture_status === "stuck_adjust") {
    return userFacingInstructionText(response.ui_hint ?? `${REASON_COPY[response.reason] ?? "Arah wajah belum sesuai."} Tetap di dalam oval.`);
  }
  if (String(response.reason ?? "").startsWith("pose_mismatch") && response.ui_hint) {
    return userFacingInstructionText(response.ui_hint);
  }
  return userFacingInstructionText(REASON_COPY[response.reason] ?? response.ui_hint ?? "Sesuaikan wajah dan coba lagi.");
}

function poseArrow(pose, quality = null) {
  // left_20/right_20 are backend yaw poses from the raw camera frame. Only the
  // visual arrow is flipped for a mirrored preview; the requested pose sent to
  // /enroll/frame is never changed by UI mirroring.
  if (pose === "left_20") {
    return arrowDescriptor(getUserFacingDirection("left"), "turn");
  }
  if (pose === "right_20") {
    return arrowDescriptor(getUserFacingDirection("right"), "turn");
  }
  if (pose === "up_or_down") {
    return arrowDescriptor(quality?.pose_pitch && quality.pose_pitch > 0 ? "down" : "up", "chin");
  }
  return null;
}

function responseLooksNearlyReady(response) {
  const flags = response?.quality?.flags ?? {};
  const coreReady =
    flags.exactly_one_face &&
    flags.max_faces_respected !== false &&
    flags.min_face_width &&
    flags.min_brightness &&
    flags.min_blur_score &&
    flags.min_contrast !== false &&
    flags.overexposed_ratio !== false &&
    flags.underexposed_ratio !== false &&
    flags.liveness_threshold !== false;
  const centered = flags.face_centered_x && flags.face_centered_y;
  const poseReady = response?.pose_valid !== false && !String(response?.reason ?? "").startsWith("pose_mismatch");
  return Boolean(coreReady && centered && poseReady);
}

function stateFromFrameResponse(response) {
  if (!response) {
    return "searching_face";
  }
  if (response.accepted) {
    return "pose_complete";
  }
  if (response.capture_status === "stuck_adjust") {
    return "stuck_adjust";
  }
  if (response.capture_status === "pose_complete") {
    return "pose_complete";
  }
  if (response.pose_status === "no_face") {
    return "searching_face";
  }
  const flags = response.quality?.flags ?? {};
  if (flags.exactly_one_face === false || !response.quality?.face_width_px) {
    return "searching_face";
  }
  return responseLooksNearlyReady(response) ? "holding" : "adjusting_position";
}

function scheduleAfterAcceptedFrame(previousPose, response) {
  clearTransitionTimer();
  state.displayPose = previousPose;
  if (allPosesComplete()) {
    return;
  }

  state.transitionTimerId = window.setTimeout(() => {
    state.transitionTimerId = null;
    if (!state.enrollmentSessionId || state.requestInFlight || state.enrollmentState === "finishing") {
      return;
    }

    const nextPose = response.next_pose;
    const poseChanged = nextPose && nextPose !== previousPose;
    state.lastFrameResponse = null;
    state.stableSince = poseChanged ? null : Date.now();

    if (poseChanged) {
      state.displayPose = nextPose;
      setEnrollmentState("next_pose");
      state.captureStatus = "next_pose";
      state.uiHint = `Lanjut ke ${poseTitle(nextPose)}.`;
      renderWizard();

      state.transitionTimerId = window.setTimeout(() => {
        state.transitionTimerId = null;
        if (!state.enrollmentSessionId || state.requestInFlight || state.enrollmentState === "finishing") {
          return;
        }
        state.displayPose = null;
        state.captureStatus = "searching_face";
        state.uiHint = `${poseInstruction(nextPose)} Posisikan wajah di dalam oval.`;
        setEnrollmentState("searching_face");
        renderWizard();
      }, AFTER_ACCEPT_DELAY_MS);
      return;
    }

    state.displayPose = null;
    state.captureStatus = "holding";
    state.uiHint = "Bagus, tetap diam.";
    setEnrollmentState("holding");
    renderWizard();
  }, AFTER_ACCEPT_DELAY_MS);
}

function guideToneFor(response) {
  if (!response) {
    return state.enrollmentSessionId ? "danger" : "idle";
  }
  if (response.accepted) {
    return "success";
  }
  if (response.capture_status === "stuck_adjust") {
    return "warning";
  }
  if (response.pose_status === "no_face") {
    return "danger";
  }
  if (state.requestInFlight && responseLooksNearlyReady(response)) {
    return "success";
  }
  if (state.requestInFlight) {
    return "warning";
  }
  if (distanceState(response).key === "ideal" && responseLooksNearlyReady(response)) {
    return "success";
  }
  if (responseLooksNearlyReady(response)) {
    return "warning";
  }
  return "danger";
}

function guidanceFromResponse(response) {
  const pose = currentPose();
  if (state.requestInFlight) {
    return { instruction: "Merekam...", arrow: null, secondary: "Tetap diam" };
  }
  if (!state.enrollmentSessionId) {
    return { instruction: "Posisikan wajah di tengah", arrow: null, secondary: "Kamera siap" };
  }
  if (!response) {
    return { instruction: "Posisikan wajah di dalam oval", arrow: null, secondary: poseInstruction(pose) };
  }
  if (response.accepted) {
    return { instruction: "Berhasil direkam", arrow: null, secondary: response.next_pose ? "Lanjut ke pose berikutnya" : "Semua pose selesai" };
  }

  if (response.capture_status === "stuck_adjust") {
    const arrow = arrowFromGuidanceDirection(response.guidance_direction) ?? poseArrow(pose, response.quality);
    return { instruction: response.ui_hint || "Arah wajah belum sesuai.", arrow, secondary: "Tetap di dalam oval" };
  }

  if (response.pose_status === "no_face") {
    return { instruction: "Posisikan wajah di dalam oval", arrow: null, secondary: "Cari wajah..." };
  }

  const quality = response.quality;
  const flags = quality?.flags ?? {};
  if (flags.exactly_one_face === false) {
    return {
      instruction: quality?.face_width_px ? "Hanya satu wajah" : "Posisikan wajah di dalam oval",
      arrow: null,
      secondary: "Pastikan wajah terlihat jelas",
    };
  }
  if (flags.min_face_width === false) {
    return { instruction: "Dekatkan wajah", arrow: null, secondary: "Wajah masih terlalu jauh" };
  }
  const distance = distanceState(response);
  if (distance.key === "too_close") {
    return { instruction: distance.label, arrow: null, secondary: "Beri sedikit jarak dari kamera" };
  }
  if (flags.min_brightness === false || flags.underexposed_ratio === false) {
    return { instruction: "Tambah cahaya", arrow: null, secondary: "Wajah terlalu gelap" };
  }
  if (flags.overexposed_ratio === false) {
    return { instruction: "Kurangi cahaya", arrow: null, secondary: "Wajah terlalu terang" };
  }
  if (flags.min_blur_score === false) {
    return { instruction: "Tahan...", arrow: null, secondary: "Jangan bergerak" };
  }
  if (flags.face_centered_x === false && quality) {
    const arrow = horizontalDirection(quality.face_center_offset_x);
    return { instruction: movementInstruction(arrow), arrow: arrowDescriptor(arrow, "move"), secondary: "Tetap di dalam oval" };
  }
  if (flags.face_centered_y === false && quality) {
    const arrow = verticalDirection(quality.face_center_offset_y);
    return { instruction: movementInstruction(arrow), arrow: arrowDescriptor(arrow, "move"), secondary: "Tetap di dalam oval" };
  }
  if (response.pose_valid === false) {
    const arrow = arrowFromGuidanceDirection(response.guidance_direction) ?? poseArrow(pose, quality);
    return { instruction: localizedHint(response), arrow, secondary: poseInstruction(pose) };
  }
  if (response.reason === "liveness_below_threshold") {
    return { instruction: "Tahan...", arrow: null, secondary: "Lihat kamera dengan alami" };
  }
  if (distance.key === "ideal") {
    return { instruction: "Tahan...", arrow: null, secondary: "Bagus, tetap diam" };
  }
  return { instruction: localizedHint(response) || poseInstruction(pose), arrow: null, secondary: "Ikuti panduan" };
}

function renderGuideGeometry(response) {
  const quality = response?.quality;
  if (!quality || !quality.face_width_px) {
    elements.faceOval.style.removeProperty("--oval-width");
    elements.faceOval.style.removeProperty("--oval-height");
    elements.faceOval.style.removeProperty("--oval-x");
    elements.faceOval.style.removeProperty("--oval-y");
    return;
  }

  const videoWidth = elements.camera.videoWidth || 640;
  const videoHeight = elements.camera.videoHeight || 480;
  const width = clamp(quality.face_width_px * 1.38, videoWidth * 0.28, videoWidth * 0.54);
  const height = clamp(width * 1.32, videoHeight * 0.42, videoHeight * 0.82);
  const visualOffsetX = VIDEO_PREVIEW_MIRRORED ? -quality.face_center_offset_x : quality.face_center_offset_x;
  const shiftX = clamp(visualOffsetX * 42, -54, 54);
  const shiftY = clamp(quality.face_center_offset_y * 32, -44, 44);

  elements.faceOval.style.setProperty("--oval-width", `${width}px`);
  elements.faceOval.style.setProperty("--oval-height", `${height}px`);
  elements.faceOval.style.setProperty("--oval-x", `${shiftX}px`);
  elements.faceOval.style.setProperty("--oval-y", `${shiftY}px`);
}

function playAcceptedFeedback() {
  elements.cameraStage.classList.add("flash-success");
  elements.successBurst.classList.add("is-visible");
  window.setTimeout(() => {
    elements.cameraStage.classList.remove("flash-success");
    elements.successBurst.classList.remove("is-visible");
  }, 420);
}

function showLivenessChallenge() {
  state.livenessChallengeAttempts = 0;
  requestLivenessChallenge();
}

function hideLivenessChallenge() {
  state.livenessChallengeActive = false;
  state.livenessChallengeId = null;
  state.livenessChallengeColor = null;
  state.livenessChallengeLabel = "";
  if (state.livenessChallengeTimerId) {
    window.clearInterval(state.livenessChallengeTimerId);
    state.livenessChallengeTimerId = null;
  }
  elements.challengeOverlay.classList.add("is-hidden");
}

async function requestLivenessChallenge() {
  try {
    const challenge = await postJson("/liveness/challenge", { device_code: DEVICE_CODE });
    state.livenessChallengeId = challenge.challenge_id;
    state.livenessChallengeColor = challenge.display_rgb;
    state.livenessChallengeLabel = challenge.color_label;
    state.livenessChallengeExpiresAt = Date.now() + challenge.expires_at_seconds * 1000;
    state.livenessChallengeActive = true;
    state.livenessChallengeAttempts += 1;
    const rgb = challenge.display_rgb;
    elements.challengeSwatch.style.background = `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
    elements.challengeText.textContent = `Tunjukkan benda berwarna ${challenge.color_label}`;
    elements.challengeOverlay.classList.remove("is-hidden");
    if (state.livenessChallengeTimerId) {
      window.clearInterval(state.livenessChallengeTimerId);
    }
    state.livenessChallengeTimerId = window.setInterval(updateLivenessChallengeCountdown, 200);
    window.setTimeout(() => attemptLivenessCapture(), 1200);
  } catch (error) {
    if (authFailureError(error)) {
      return;
    }
    console.warn("Liveness challenge request failed", error);
    state.livenessChallengeId = null;
    state.livenessChallengeActive = false;
  }
}

function updateLivenessChallengeCountdown() {
  const remaining = Math.max(0, Math.ceil((state.livenessChallengeExpiresAt - Date.now()) / 1000));
  elements.challengeCountdown.textContent = String(remaining);
  if (remaining <= 0) {
    hideLivenessChallenge();
  }
}

async function attemptLivenessCapture() {
  if (!state.livenessChallengeActive || !state.livenessChallengeId) {
    finishLivenessChallenge(false);
    return;
  }
  if (Date.now() >= state.livenessChallengeExpiresAt) {
    hideLivenessChallenge();
    return;
  }
  try {
    const frame = captureSingleFrame({ quality: 0.8, maxWidth: 640 });
    const result = await postJson("/liveness/verify", {
      challenge_id: state.livenessChallengeId,
      device_code: DEVICE_CODE,
      frame_b64: frame,
    });
    if (result.passed) {
      finishLivenessChallenge(true, result);
    } else if (result.remaining_attempts <= 0) {
      finishLivenessChallenge(false, result);
    } else {
      window.setTimeout(() => attemptLivenessCapture(), 800);
    }
  } catch (error) {
    if (authFailureError(error)) {
      return;
    }
    console.warn("Liveness capture failed", error);
    if (state.livenessChallengeAttempts < 3) {
      window.setTimeout(() => requestLivenessChallenge(), 1000);
    } else {
      finishLivenessChallenge(false);
    }
  }
}

function finishLivenessChallenge(passed, result = null) {
  hideLivenessChallenge();
  if (passed && result) {
    state.uiHint = "Wajah asli terverifikasi.";
  } else {
    state.uiHint = "Tunjukkan benda berwarna yang diminta.";
  }
  if (state.enrollmentSessionId && !allPosesComplete()) {
    renderWizard();
  }
}

function formatConfidence(confidence) {
  return typeof confidence === "number" && Number.isFinite(confidence) ? `${Math.round(confidence * 100)}%` : "-";
}

function currentTimeText() {
  return new Intl.DateTimeFormat("id-ID", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date());
}

function currentDateText() {
  return new Intl.DateTimeFormat("id-ID", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date());
}

function initialsFor(person) {
  const source = String(person?.full_name || person?.student_id || "?").trim();
  const words = source.split(/\s+/).filter(Boolean);
  if (!words.length) {
    return "?";
  }
  return words
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
}

function attendanceEndpoint() {
  return "/attendance/preview";
}

function attendancePayload(frames) {
  const payloadFrames = frames.map((frame) => ({ frame_b64: frame.frame_b64 }));
  return {
    device_code: DEVICE_CODE,
    frames: payloadFrames,
    session_id: state.selectedAttendanceSessionId ?? null,
  };
}

function qualitySummaryFromResponse(response) {
  return response?.quality_summary ?? null;
}

function responseRecognitionStatus(response) {
  const legacyDecision = response?.decision;
  return response?.recognition_status ?? (
    ["recognized", "cooldown", "unknown", "session_inactive", "no_matching_session", "multiple_matching_sessions"].includes(legacyDecision)
      ? legacyDecision
      : legacyDecision === "accepted" && response?.person
        ? "recognized"
        : legacyDecision === "rejected"
          ? "rejected"
          : null
  );
}

function responseIsRecognized(response) {
  return responseRecognitionStatus(response) === "recognized";
}

function responseIsCooldown(response) {
  return responseRecognitionStatus(response) === "cooldown" || response?.reason === "cooldown" || response?.reason === "person_on_cooldown";
}

function attendanceDecisionLabel(decision, reason = "") {
  const labels = {
    accepted: "Diterima",
    rejected: "Ditolak",
    manual_approved: "Disetujui Manual",
    manual_rejected: "Ditolak Manual",
  };
  const detail = REASON_COPY[reason] || (reason ? reason.replaceAll("_", " ") : "");
  const label = detail && decision === "rejected" ? `${labels[decision] ?? decision} - ${detail}` : (labels[decision] ?? decision ?? "-");
  return escapeHtml(label);
}

function isQualityReason(reason) {
  return Boolean(reason && QUALITY_GUIDANCE_COPY[normalizeQualityReason(reason)]);
}

function dominantQualityReason(response) {
  const summary = qualitySummaryFromResponse(response);
  const dominant = normalizeQualityReason(summary?.dominant_reason);
  if (isQualityReason(dominant) && dominant !== "accepted") {
    return dominant;
  }
  const responseReason = normalizeQualityReason(response?.reason);
  return isQualityReason(responseReason) ? responseReason : null;
}

function qualityFramesFromResponse(response) {
  const frames = qualitySummaryFromResponse(response)?.frames;
  return Array.isArray(frames) ? frames : [];
}

function strongestFaceFrame(response) {
  return qualityFramesFromResponse(response).reduce((best, frame) => {
    const width = Number(frame?.face_width_px ?? 0);
    const bestWidth = Number(best?.face_width_px ?? 0);
    return width > bestWidth ? frame : best;
  }, null);
}

function attendanceFaceWidthRatio(response) {
  const frame = strongestFaceFrame(response);
  const faceWidth = Number(frame?.face_width_px ?? 0);
  const minFaceWidth = Number(frame?.min_face_width_px ?? 0);
  if (!faceWidth || !minFaceWidth) {
    return null;
  }
  return faceWidth / minFaceWidth;
}

function isQualityRejection(response) {
  const reason = dominantQualityReason(response);
  if (!reason) {
    return false;
  }
  if (response?.reason === "all_frames_rejected") {
    return true;
  }
  const summary = qualitySummaryFromResponse(response);
  return Boolean(summary?.rejected_frames && !summary?.accepted_frames && !responseIsRecognized(response));
}

function qualityGuidanceMessage(response) {
  const reason = dominantQualityReason(response);
  if (reason === "face_too_small") {
    const ratio = attendanceFaceWidthRatio(response);
    if (ratio !== null && ratio >= 0.85) {
      return "Sedikit lagi, dekatkan wajah";
    }
  }
  return QUALITY_GUIDANCE_COPY[reason] ?? "Sesuaikan wajah dan coba lagi";
}

function qualitySecondaryMessage(response) {
  const reason = dominantQualityReason(response);
  return QUALITY_SECONDARY_COPY[reason] ?? "Tahan sebentar sampai frame siap diproses.";
}

function qualityTone(response) {
  const reason = dominantQualityReason(response);
  return ["multiple_faces_detected", "liveness_below_threshold", "liveness_failed"].includes(reason) ? "danger" : "warning";
}

function recognitionRejectionMessage(response) {
  if (response?.reason === "candidate_margin_too_small") {
    return "Data wajah terlalu mirip. Coba ulangi posisi wajah.";
  }
  if (response?.reason === "multi_frame_confirm_failed") {
    return "Wajah belum stabil, tahan sebentar";
  }
  if (response?.reason === "no_match_within_threshold" || response?.reason === "distance_above_threshold") {
    return "Wajah tidak dikenali";
  }
  if (response?.reason === "confidence_below_threshold") {
    return "Wajah tidak dikenali";
  }
  return "Coba lagi";
}

function attendanceMessageFromResponse(response) {
  if (!response) {
    return "Posisikan wajah di dalam oval";
  }
  if (isQualityRejection(response)) {
    return qualityGuidanceMessage(response);
  }
  if (response.reason === "candidate_margin_too_small") {
    return "Data wajah terlalu mirip. Coba ulangi posisi wajah.";
  }
  const recognitionStatus = responseRecognitionStatus(response);
  if (recognitionStatus === "recognized") {
    return "Wajah dikenali. Periksa detail sebelum mencatat absensi.";
  }
  if (recognitionStatus === "no_matching_session") {
    return "Wajah dikenali, tetapi tidak ada sesi absensi yang sesuai untuk kelas dan waktu saat ini.";
  }
  if (recognitionStatus === "multiple_matching_sessions") {
    return "Ditemukan lebih dari satu sesi yang sesuai. Hubungi admin.";
  }
  if (responseIsCooldown(response)) {
    return "Tunggu sebentar sebelum mencoba lagi";
  }
  if (recognitionStatus === "session_inactive") {
    return "Sesi absensi sudah tidak aktif";
  }
  if (recognitionStatus === "unknown" || response.decision === "rejected") {
    return recognitionRejectionMessage(response);
  }
  return "Coba lagi";
}

function attendancePanelStatusMessage(status) {
  if (status === "recognizing") {
    return "Tahan sebentar saat sistem mengenali wajah.";
  }
  if (status === "recognized" || status === "confirming") {
    return "Periksa detail absensi.";
  }
  if (status === "scanning") {
    return "Arahkan wajah ke oval.";
  }
  if (status === "no_matching_session") {
    return "Tidak ada sesi absensi yang sesuai untuk kelas dan waktu saat ini.";
  }
  if (status === "multiple_matching_sessions") {
    return "Ditemukan lebih dari satu sesi yang sesuai. Hubungi admin.";
  }
  if (status === "quality_rejected") {
    return qualityGuidanceMessage(state.attendanceLastResponse);
  }
  return attendanceMessageFromResponse(state.attendanceLastResponse);
}

function setAttendanceResultTone(tone) {
  elements.attendanceResultCard.classList.remove("success", "recognized", "unknown", "ambiguous", "cooldown", "error", "guidance");
  if (tone) {
    elements.attendanceResultCard.classList.add(tone);
  }
}

const TOAST_ICONS = {
  success: "&#10003;",
  warning: "&#9888;",
  error: "&#10060;",
  info: "&#8505;",
};

// Short WebAudio cue so someone walking past a gate kiosk gets feedback
// without reading the screen. Lazily created after the first user gesture so
// browsers don't block the AudioContext.
let sharedAudioContext = null;

function playFeedbackTone(kind) {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    if (!sharedAudioContext) sharedAudioContext = new AudioCtx();
    const ctx = sharedAudioContext;
    if (ctx.state === "suspended") ctx.resume().catch(() => {});
    // success: rising two-tone; warning: single mid; error: low buzz.
    const sequence = kind === "success" ? [660, 990] : kind === "error" ? [220] : [440];
    const now = ctx.currentTime;
    sequence.forEach((freq, index) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = kind === "error" ? "sawtooth" : "sine";
      osc.frequency.value = freq;
      const start = now + index * 0.12;
      const stop = start + 0.11;
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(0.2, start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, stop);
      osc.connect(gain).connect(ctx.destination);
      osc.start(start);
      osc.stop(stop + 0.02);
    });
  } catch {
    // Audio is a non-critical enhancement; ignore failures.
  }
}

let attendanceToastTimer = null;

function hideAttendanceToast() {
  if (attendanceToastTimer) {
    clearTimeout(attendanceToastTimer);
    attendanceToastTimer = null;
  }
  if (elements.attendanceToast) {
    elements.attendanceToast.classList.remove("visible");
  }
}

function showAttendanceToast(type, message, timeoutMs = 2200) {
  hideAttendanceToast();
  if (!elements.attendanceToast || !elements.attendanceToastIcon || !elements.attendanceToastText) return;
  playFeedbackTone(type);
  elements.attendanceToast.className = `attendance-toast ${type}`;
  elements.attendanceToastIcon.innerHTML = TOAST_ICONS[type] ?? TOAST_ICONS.info;
  elements.attendanceToastText.textContent = message;
  requestAnimationFrame(() => {
    elements.attendanceToast.classList.add("visible");
  });
  attendanceToastTimer = setTimeout(hideAttendanceToast, timeoutMs);
}

let attendanceEdgeSheetHandler = null;

function hideAttendanceEdgeSheet() {
  if (elements.attendanceEdgeSheet) {
    elements.attendanceEdgeSheet.classList.remove("visible");
    setTimeout(() => {
      elements.attendanceEdgeSheet.classList.add("is-hidden");
    }, 320);
  }
  attendanceEdgeSheetHandler = null;
}

function showAttendanceEdgeSheet({ title, message, actions }) {
  if (!elements.attendanceEdgeSheet || !elements.attendanceEdgeTitle || !elements.attendanceEdgeMessage || !elements.attendanceEdgeActions) return;
  hideAttendanceEdgeSheet();
  elements.attendanceEdgeTitle.textContent = title;
  elements.attendanceEdgeMessage.textContent = message;
  elements.attendanceEdgeActions.innerHTML = "";
  if (actions && actions.length > 0) {
    actions.forEach((action) => {
      const btn = document.createElement("button");
      btn.className = `edge-btn ${action.variant || "primary"}`;
      btn.textContent = action.label;
      btn.addEventListener("click", () => {
        hideAttendanceEdgeSheet();
        if (action.handler) action.handler();
      });
      elements.attendanceEdgeActions.appendChild(btn);
    });
  }
  requestAnimationFrame(() => {
    elements.attendanceEdgeSheet.classList.remove("is-hidden");
    requestAnimationFrame(() => {
      elements.attendanceEdgeSheet.classList.add("visible");
    });
  });
}

function renderAttendanceResultCard() {
  const response = state.attendanceLastResponse;
  const cardStatus = state.attendanceRequestInFlight ? "recognizing" : state.attendanceStatus;
  const showCard =
    state.mode === "recognize" ||
    [
      "accepted",
      "recognized",
      "confirming",
      "quality_rejected",
      "unknown",
      "ambiguous",
      "cooldown",
      "session_inactive",
      "no_matching_session",
      "multiple_matching_sessions",
      "error",
    ].includes(cardStatus);
  elements.attendanceResultCard.classList.toggle("is-hidden", !showCard);
  elements.attendanceResultCard.classList.toggle("visible", showCard);
  if (!showCard) {
    return;
  }

  const person = response?.person ?? null;
  const known = Boolean(person);
  const titles = {
    loading_sessions: "Memuat sesi absensi",
    recognizing: "Mengenali wajah",
    scanning: "Arahkan wajah ke oval",
    no_session: "Pengenalan wajah saja",
    quality_rejected: "Sesuaikan posisi",
    accepted: "Absensi berhasil",
    recognized: "Konfirmasi absensi",
    confirming: "Mencatat absensi",
    ambiguous: "Data wajah terlalu mirip",
    cooldown: "Tunggu sebentar",
    session_inactive: "Sesi belum aktif",
    no_matching_session: "Tidak ada sesi sesuai",
    multiple_matching_sessions: "Sesi ganda",
    error: "Gangguan koneksi",
  };
  const title = titles[cardStatus] ?? "Wajah tidak dikenali";
  const message = cardStatus === "error" ? state.uiHint : attendancePanelStatusMessage(cardStatus);
  const tones = {
    accepted: "success",
    recognized: "recognized",
    ambiguous: "ambiguous",
    cooldown: "cooldown",
    error: "error",
    session_inactive: "unknown",
    no_matching_session: "unknown",
    multiple_matching_sessions: "unknown",
    quality_rejected: qualityTone(response) === "danger" ? "unknown" : "guidance",
    unknown: "unknown",
  };
  const tone = tones[cardStatus] ?? null;

  setAttendanceResultTone(tone);
  elements.attendanceCardTitle.textContent = "";
  elements.attendanceName.textContent = known ? person.full_name : title;
  elements.attendanceStudent.textContent = known ? `${person.student_id}${person.class_code ? ` - ${person.class_code}` : ""}` : "";
  elements.attendanceConfidence.textContent = "";
  elements.attendanceDate.textContent = "";
  elements.attendanceTime.textContent = "";
  const resolvedSession = response?.resolved_session ?? state.pendingAttendance?.response?.resolved_session ?? null;
  elements.attendanceSession.textContent = "";
  elements.attendanceMessage.textContent = message;

  const backendCrop = response?.captured_face_b64 ? `data:image/jpeg;base64,${response.captured_face_b64}` : null;
  const thumbnail = known ? backendCrop ?? state.attendanceThumbnail : null;
  elements.attendancePhoto.classList.toggle("is-hidden", !thumbnail);
  elements.attendanceAvatar.classList.toggle("is-hidden", Boolean(thumbnail));
  if (thumbnail) {
    elements.attendancePhoto.src = thumbnail;
  } else {
    elements.attendancePhoto.removeAttribute("src");
    elements.attendanceAvatar.textContent = known ? initialsFor(person) : "?";
  }

  const cooldownRemaining = Math.max(0, Math.ceil((state.attendanceCooldownUntil - Date.now()) / 1000));
  const showCooldown = cooldownRemaining > 0 || response?.cooldown_remaining_seconds;
  elements.attendanceCooldown.classList.toggle("is-hidden", !showCooldown);
  if (showCooldown) {
    elements.attendanceCooldown.textContent = `Tunggu ${cooldownRemaining || response.cooldown_remaining_seconds} detik`;
  }
}

function renderAttendance() {
  const response = state.attendanceLastResponse;
  const scanning = state.attendanceStatus === "scanning" || state.attendanceStatus === "no_session";
  const recognizing = state.attendanceRequestInFlight || state.attendanceStatus === "recognizing" || state.attendanceConfirmInFlight;
  const ambiguous = response?.reason === "candidate_margin_too_small" || state.attendanceStatus === "ambiguous";
  const qualityRejected = state.attendanceStatus === "quality_rejected" || isQualityRejection(response);
  const noSession = !state.selectedAttendanceSessionId;
  let instruction = "Posisikan wajah di dalam oval";
  if (noSession) instruction = "Pilih sesi absensi untuk mulai";
  else if (recognizing) instruction = state.attendanceConfirmInFlight ? "Mencatat absensi..." : "Mengenali wajah...";
  else if (qualityRejected) instruction = qualityGuidanceMessage(response);
  else if (ambiguous) instruction = "Data wajah terlalu mirip";
  else if (state.attendanceStatus === "accepted") instruction = "Absensi berhasil";
  else if (state.attendanceStatus === "recognized") instruction = "Konfirmasi absensi";
  else if (state.attendanceStatus === "no_matching_session") instruction = "Tidak ada sesi sesuai";
  else if (state.attendanceStatus === "multiple_matching_sessions") instruction = "Sesi ganda";
  else if (state.attendanceStatus === "not_in_selected_class") instruction = "Wajah tidak terdaftar pada kelas ini";
  else if (state.attendanceStatus === "unknown") instruction = attendanceMessageFromResponse(response);
  else if (state.attendanceStatus === "cooldown") instruction = "Tunggu sebentar";
  else if (state.attendanceStatus === "session_inactive") instruction = "Sesi tidak aktif";
  else if (state.attendanceStatus === "error") instruction = state.uiHint;

  let secondary = "";
  if (recognizing) secondary = "Tahan sebentar...";
  else if (qualityRejected) secondary = qualitySecondaryMessage(response);
  else if (scanning && !noSession) secondary = "Mencari wajah...";
  else if (noSession) secondary = "";
  else if (response?.resolved_session) secondary = resolvedSessionLabel(response.resolved_session, { includeCode: false });
  const tone =
    state.attendanceStatus === "accepted" || state.attendanceStatus === "recognized"
      ? "success"
      : qualityRejected
        ? qualityTone(response)
      : recognizing || scanning || state.attendanceStatus === "cooldown" || noSession
        ? "warning"
        : "danger";

  elements.cameraStage.dataset.guideTone = tone;
  elements.cameraStage.dataset.flowState = recognizing ? "capturing" : scanning ? "holding" : state.attendanceStatus;
  elements.ovalPrimary.textContent = recognizing ? "Mengenali..." : scanning ? "" : instruction;
  elements.ovalSecondary.textContent = secondary;

  // Top bar with session info
  if (elements.attendanceTopBar && elements.attendanceSessionBadge) {
    const session = selectedAttendanceSession();
    if (session) {
      elements.attendanceSessionBadge.textContent = attendanceSessionLabel(session, { includeClass: false });
      elements.attendanceTopBar.classList.remove("is-hidden");
    } else if (state.selectedAttendanceClassId) {
      const cls = state.availableAttendanceClasses.find((c) => c.class_id === state.selectedAttendanceClassId);
      elements.attendanceSessionBadge.textContent = cls ? `${cls.class_code} - ${cls.class_name}` : "Memuat sesi...";
      elements.attendanceTopBar.classList.remove("is-hidden");
    } else if (state.attendanceStatus === "session_inactive" || state.attendanceStatus === "no_matching_session" || noSession) {
      elements.attendanceSessionBadge.textContent = noSession ? "Pilih Kelas" : "Tidak ada sesi aktif";
      elements.attendanceTopBar.classList.remove("is-hidden");
    } else {
      elements.attendanceTopBar.classList.add("is-hidden");
    }
  }

  renderAttendanceSessionPicker();
  if (elements.attendanceChangeSessionBtn) {
    elements.attendanceChangeSessionBtn.classList.toggle("is-hidden", noSession);
  }
  elements.cancelButton.disabled = false;
  elements.captureButton.disabled = true;
  elements.finishButton.disabled = true;
  elements.result.textContent = "diagnostik tersembunyi";
  clearArrows();
  renderGuideGeometry(null);
  renderPoseDots();
  setStatusBadge(noSession ? "no_session" : (recognizing ? "recognizing" : state.attendanceStatus));
  renderAttendanceResultCard();
}

function renderAttendanceSessionPicker() {
  if (!elements.attendanceSessionPicker) return;
  const session = selectedAttendanceSession();
  if (session) {
    elements.attendanceSessionPicker.classList.add("is-hidden");
    elements.attendanceSessionSelect.innerHTML = "";
    return;
  }
  if (state.attendanceClassLookupInFlight) {
    elements.attendanceSessionCopy.textContent = "Memuat kelas...";
    elements.attendanceSessionPicker.classList.add("is-hidden");
    return;
  }
  if (state.attendanceClassLoadError) {
    elements.attendanceSessionCopy.textContent = state.attendanceClassLoadError;
    elements.attendanceSessionPicker.classList.add("is-hidden");
    if (state.attendanceClassesFailed404) {
      elements.attendanceSessionCopy.textContent = "Endpoint kelas absensi belum tersedia. Pastikan server berjalan.";
    }
    return;
  }
  const classes = state.availableAttendanceClasses;
  if (!classes || classes.length === 0) {
    elements.attendanceSessionCopy.textContent = "Tidak ada kelas aktif.";
    elements.attendanceSessionPicker.classList.add("is-hidden");
    return;
  }
  if (!state.selectedAttendanceClassId) {
    elements.attendanceSessionCopy.textContent = "Pilih Kelas";
    elements.attendanceSessionPicker.classList.remove("is-hidden");
    elements.attendanceSessionSelect.innerHTML = `<option value="">-- Pilih Kelas --</option>${classes
      .map((c) => `<option value="${escapeHtml(c.class_id)}">${escapeHtml(c.class_code)} - ${escapeHtml(c.class_name)}</option>`)
      .join("")}`;
    return;
  }
  const sessions = state.availableAttendanceSessions;
  if (state.attendanceSessionLookupInFlight) {
    elements.attendanceSessionCopy.textContent = "Memuat sesi...";
    elements.attendanceSessionPicker.classList.add("is-hidden");
    return;
  }
  if (state.attendanceSessionLoadError) {
    elements.attendanceSessionCopy.textContent = state.attendanceSessionLoadError;
    elements.attendanceSessionPicker.classList.add("is-hidden");
    return;
  }
  if (!sessions || sessions.length === 0) {
    elements.attendanceSessionCopy.textContent = "Tidak ada sesi aktif untuk kelas ini.";
    elements.attendanceSessionPicker.classList.remove("is-hidden");
    elements.attendanceSessionSelect.innerHTML = `<option value="">-- Tidak Ada Sesi --</option>`;
    return;
  }
  elements.attendanceSessionCopy.textContent = "Pilih Sesi";
  elements.attendanceSessionPicker.classList.remove("is-hidden");
  elements.attendanceSessionSelect.innerHTML = `<option value="">-- Pilih Sesi --</option>${sessions
    .map((s) => {
      const label = attendanceSessionLabel(s, { includeClass: false });
      return `<option value="${escapeHtml(s.session_id)}">${escapeHtml(label)}</option>`;
    })
    .join("")}`;
}

function attendancePreviewPhoto(response) {
  if (response?.captured_face_b64) {
    return `data:image/jpeg;base64,${response.captured_face_b64}`;
  }
  return state.attendanceThumbnail;
}

function showAttendanceConfirmModal(response) {
  const person = response?.person ?? {};
  const session = response?.resolved_session ?? null;
  const photo = attendancePreviewPhoto(response);
  const recognitionStatus = responseRecognitionStatus(response);
  const canConfirm = recognitionStatus === "recognized" && Boolean(session);
  state.pendingAttendance = { response, photo };
  state.attendancePausedUntil = Number.POSITIVE_INFINITY;

  elements.attendanceConfirmModal.classList.remove("is-hidden");
  elements.attendanceConfirmStatus.textContent = canConfirm ? "Dikenali" : "Perlu Ulang";
  elements.attendanceConfirmStatus.className = `status-pill ${canConfirm ? "recognized" : "unknown"}`;
  elements.confirmName.textContent = person.full_name ?? "-";
  elements.confirmClass.textContent = person.class_name ?? person.class_code ?? "-";
  elements.confirmSession.textContent = session?.session_name ?? session?.session_code ?? "-";
  const nowWita = new Date(Date.now() + 8 * 60 * 60 * 1000);
  const timeStr = nowWita.toISOString().substring(11, 16) + " WITA";
  elements.confirmTime.textContent = timeStr;
  elements.attendanceConfirmPhoto.classList.toggle("is-hidden", !photo);
  elements.attendanceConfirmAvatar.classList.toggle("is-hidden", Boolean(photo));
  if (photo) {
    elements.attendanceConfirmPhoto.src = photo;
  } else {
    elements.attendanceConfirmPhoto.removeAttribute("src");
    elements.attendanceConfirmAvatar.textContent = initialsFor(person);
  }
  elements.attendanceConfirmAccept.classList.toggle("is-hidden", !canConfirm);
  elements.attendanceConfirmAccept.disabled = !canConfirm || state.attendanceConfirmInFlight;
  elements.attendanceConfirmRetry.disabled = state.attendanceConfirmInFlight;
  if (recognitionStatus === "no_matching_session") {
    elements.attendanceConfirmMessage.textContent =
      "Wajah dikenali, tetapi tidak ada sesi absensi yang sesuai untuk kelas dan waktu saat ini.";
  } else if (recognitionStatus === "multiple_matching_sessions") {
    elements.attendanceConfirmMessage.textContent = "Ditemukan lebih dari satu sesi yang sesuai. Hubungi admin.";
  } else {
    elements.attendanceConfirmMessage.textContent = "Pastikan data sudah benar sebelum menekan Benar.";
  }
}

function hideAttendanceConfirmModal() {
  elements.attendanceConfirmModal.classList.add("is-hidden");
  elements.attendanceConfirmAccept.disabled = false;
  elements.attendanceConfirmRetry.disabled = false;
}

function discardPendingAttendance() {
  state.pendingAttendance = null;
  state.attendanceConfirmInFlight = false;
  state.attendanceLastResponse = null;
  state.attendanceStatus = "scanning";
  state.uiHint = "Arahkan wajah ke oval.";
  state.attendancePausedUntil = Date.now() + 500;
  hideAttendanceConfirmModal();
  renderAttendance();
}

function appendSuccessfulAttendance(confirmResponse) {
  const attendance = confirmResponse?.attendance ?? {};
  const person = confirmResponse?.person ?? {};
  const session = confirmResponse?.resolved_session ?? {};
  const photo = state.pendingAttendance?.photo ?? attendancePreviewPhoto(state.pendingAttendance?.response);
  state.successfulAttendances = [
    {
      id: attendance.log_id ?? `${Date.now()}`,
      photo,
      full_name: attendance.full_name ?? person.full_name ?? "-",
      student_id: attendance.student_id ?? person.student_id ?? "-",
      class_name: attendance.class_name ?? person.class_name ?? person.class_code ?? "-",
      session_name: attendance.session_name ?? session.session_name ?? "-",
      created_at: attendance.created_at ?? new Date().toISOString(),
      status: "Hadir",
    },
    ...state.successfulAttendances,
  ].slice(0, 8);
}

function renderSuccessfulAttendanceLog() {
  const items = state.successfulAttendances;
  elements.attendanceSuccessEmpty.classList.toggle("is-hidden", items.length > 0);
  const rows = items
    .map((item) => {
      const photo = item.photo
        ? `<img class="success-log-photo" src="${item.photo}" alt="" />`
        : `<span class="success-log-avatar">${escapeHtml(initialsFor(item))}</span>`;
      return `<article class="success-log-item">
        ${photo}
        <div>
          <strong>${escapeHtml(item.full_name)}</strong>
          <span>${escapeHtml(item.student_id)} - ${escapeHtml(item.class_name)}</span>
          <small>${formatTimeOnly(item.created_at)} - ${escapeHtml(item.status)}</small>
        </div>
      </article>`;
    })
    .join("");
  elements.attendanceSuccessList.innerHTML = `<p id="attendance-success-empty" class="attendance-success-empty${items.length ? " is-hidden" : ""}">Belum ada absensi berhasil</p>${rows}`;
  elements.attendanceSuccessEmpty = document.getElementById("attendance-success-empty");
}

function formatDateOnly(value) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("id-ID", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(value));
}

function datetimeLocalValue(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return localDate.toISOString().slice(0, 16);
}

function formatTimeOnly(value) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("id-ID", { hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(value));
}

function formatRepeatDays(days) {
  if (!days || days.length === 0) return "-";
  const labels = { monday: "Sen", tuesday: "Sel", wednesday: "Rab", thursday: "Kam", friday: "Jum", saturday: "Sab", sunday: "Min" };
  return days.map((d) => labels[d] || d).join(", ");
}

function formatSessionTimeRange(startTime, endTime) {
  if (!startTime && !endTime) return "-";
  const s = startTime ? String(startTime).substring(0, 5) : "-";
  const e = endTime ? String(endTime).substring(0, 5) : "-";
  return `${s}–${e}`;
}

async function loadSessionTodayLogs(sessionId) {
  const container = document.getElementById("session-today-logs-container");
  if (!container || !sessionId) return;
  container.innerHTML = `<p class="muted">Memuat log...</p>`;
  try {
    const logs = await getJson(`/attendance/sessions/${sessionId}/today-logs?timezone=Asia/Makassar`);
    if (!logs || logs.length === 0) {
      container.innerHTML = `<p class="muted">Belum ada absensi hari ini.</p>`;
      return;
    }
    const rows = logs.map((log) => {
      const photo = log.captured_image_url
        ? `<img class="face-thumb mini" src="${API_BASE_URL}${log.captured_image_url}" alt="" />`
        : `<span class="avatar-mini">?</span>`;
      return `<tr>
        <td>${photo}</td>
        <td>${escapeHtml(log.full_name ?? log.student_id ?? "-")}</td>
        <td>${escapeHtml(log.class_code ?? "-")}</td>
        <td>${formatWitaDateTime(log.created_at)}</td>
        <td>${attendanceDecisionLabel(log.decision, log.reason)}</td>
      </tr>`;
    }).join("");
    container.innerHTML = `<table class="admin-table today-logs-table"><thead><tr>
      <th style="width:52px">Foto</th><th>Nama</th><th>Kelas</th><th>Waktu Absen (WITA)</th><th>Status</th>
    </tr></thead><tbody>${rows}</tbody></table>`;
  } catch (error) {
    container.innerHTML = `<p class="muted danger">Gagal memuat log.</p>`;
  }
}

function formatWitaDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  const wita = new Date(date.getTime() + 8 * 60 * 60 * 1000);
  const dd = String(wita.getUTCDate()).padStart(2, "0");
  const mm = String(wita.getUTCMonth() + 1).padStart(2, "0");
  const yy = wita.getUTCFullYear();
  const hh = String(wita.getUTCHours()).padStart(2, "0");
  const min = String(wita.getUTCMinutes()).padStart(2, "0");
  return `${dd}/${mm}/${yy} ${hh}.${min} WITA`;
}

function suggestedSessionCode() {
  const now = new Date();
  const yy = String(now.getFullYear()).slice(-2);
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const dd = String(now.getDate()).padStart(2, "0");
  const hh = String(now.getHours()).padStart(2, "0");
  const min = String(now.getMinutes()).padStart(2, "0");
  return `ABS-${yy}${mm}${dd}-${hh}${min}`;
}

function formatPercent(value) {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "-";
}

function readCookie(name) {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name.replace(/([.$?*|{}()\[\]\\\/+^])/g, "\\$1")}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

function getCookie(name) {
  const cookies = document.cookie ? document.cookie.split(";") : [];
  for (const cookie of cookies) {
    const trimmed = cookie.trim();
    if (trimmed.startsWith(`${name}=`)) {
      return decodeURIComponent(trimmed.slice(name.length + 1));
    }
  }
  return "";
}

function isUnsafeMethod(method) {
  return ["POST", "PUT", "PATCH", "DELETE"].includes(String(method).toUpperCase());
}

function csrfToken() {
  return getCookie("csrf_token");
}

function authSessionReady() {
  return Boolean(state.adminUser) && Boolean(csrfToken());
}

const PUBLIC_ATTENDANCE_PATHS = new Set([
  "/attendance/sessions/active",
  "/attendance/preview",
  "/attendance/confirm",
  "/attendance/checkin",
  "/attendance/status",
]);

function isPublicAttendancePath(path) {
  const normalized = path.split("?")[0];
  return PUBLIC_ATTENDANCE_PATHS.has(normalized) || normalized.startsWith("/attendance/sessions/") || normalized.startsWith("/attendance/logs/");
}

function requestNeedsReadySession(method, path) {
  if (!isUnsafeMethod(method)) return false;
  if (path === "/auth/login") return false;
  if (isPublicAttendancePath(path)) return false;
  return true;
}

function intendedModeAfterAuth() {
  return ["recognize", "enroll"].includes(state.mode) ? state.mode : "recognize";
}

function handleAuthRequired(message = SESSION_NOT_READY_MESSAGE, { intendedMode = intendedModeAfterAuth() } = {}) {
  stopAutoCaptureLoop();
  stopAttendanceLoop();
  state.adminUser = null;
  state.pendingModeAfterLogin = ["recognize", "enroll", "admin"].includes(intendedMode) ? intendedMode : "recognize";
  state.attendanceStatus = "idle";
  state.captureStatus = state.enrollmentSessionId ? "idle" : state.captureStatus;
  state.uiHint = message;
  state.enrollmentFrameInFlight = false;
  state.requestInFlight = false;
  updateAuthUi();
  showLogin(message);
}

function ensureUnsafeRequestAllowed(method, path) {
  if (!requestNeedsReadySession(method, path) || authSessionReady()) {
    return;
  }
  handleAuthRequired(SESSION_NOT_READY_MESSAGE);
  throw new ApiError(SESSION_NOT_READY_MESSAGE, { status: state.adminUser ? 403 : 401, url: `${API_BASE_URL}${path}` });
}

function shouldStopForAuthFailure(path, status) {
  if (isPublicAttendancePath(path)) return false;
  return path !== "/auth/login" && (status === 401 || status === 403);
}

function retryAfterMs(response) {
  const value = response.headers?.get?.("Retry-After");
  if (!value) {
    return null;
  }
  const seconds = Number(value);
  if (Number.isFinite(seconds)) {
    return Math.max(0, seconds * 1000);
  }
  const retryAt = Date.parse(value);
  return Number.isFinite(retryAt) ? Math.max(0, retryAt - Date.now()) : null;
}

function csrfHeaders(method) {
  if (!isUnsafeMethod(method)) return {};
  const token = csrfToken();
  return { "x-csrf-token": token };
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function statusBadge(label, tone = "neutral") {
  return `<span class="admin-badge ${tone}">${label}</span>`;
}

function enrollmentStatus(item) {
  if (item.primary_template_id && item.is_active) return statusBadge("Terdaftar", "success");
  if (item.sample_count > 0 && !item.primary_template_id) return statusBadge("Wajah Dihapus", "danger");
  return statusBadge("Belum Terdaftar", "warning");
}

function activeStatus(item) {
  return item.is_active ? statusBadge("Aktif", "success") : statusBadge("Nonaktif", "danger");
}

function sessionStatus(item) {
  if (item.is_deleted) return statusBadge("Diarsipkan", "warning");
  return item.is_active ? statusBadge("Aktif", "success") : statusBadge("Nonaktif", "danger");
}

function sessionMatchesAdminFilters(item) {
  const filters = state.adminSessionFilters;
  if (!filters.include_deleted && item.is_deleted) return false;
  if (filters.class_id && item.class_id !== filters.class_id) return false;
  if (filters.status === "active" && (!item.is_active || item.is_deleted)) return false;
  if (filters.status === "inactive" && (item.is_active || item.is_deleted)) return false;
  if (filters.status === "deleted" && !item.is_deleted) return false;
  if (filters.date) {
    const selected = filters.date;
    const dates = [item.starts_at, item.ends_at].filter(Boolean).map((value) => datetimeLocalValue(value).slice(0, 10));
    if (dates.length && !dates.includes(selected)) return false;
  }
  return true;
}

function updateAuthUi() {
  const loggedIn = Boolean(state.adminUser);
  elements.enrollModeButton.disabled = !loggedIn;
  elements.homeEnrollButton.disabled = !loggedIn;
  elements.homeEnrollButton.querySelector("small").textContent = loggedIn ? "Perekaman wajah otomatis" : "Login admin diperlukan";
  elements.adminLogoutButton.classList.toggle("is-hidden", !loggedIn);
  elements.adminModeButton.textContent = loggedIn ? "Panel Admin" : "Login Admin";
}

function showLogin(message = "") {
  stopAutoCaptureLoop();
  stopAttendanceLoop();
  state.mode = "login";
  elements.enrollModeButton.classList.remove("is-active");
  elements.recognizeModeButton.classList.remove("is-active");
  elements.adminModeButton.classList.add("is-active");
  if (message) {
    elements.loginError.textContent = message;
    elements.loginError.classList.remove("is-hidden");
  } else {
    elements.loginError.classList.add("is-hidden");
  }
  setScreen("login");
}

async function openAdmin() {
  stopAutoCaptureLoop();
  stopAttendanceLoop();
  if (!authSessionReady()) {
    state.pendingModeAfterLogin = "admin";
    handleAuthRequired(SESSION_NOT_READY_MESSAGE, { intendedMode: "admin" });
    return;
  }
  state.mode = "admin";
  elements.enrollModeButton.classList.remove("is-active");
  elements.recognizeModeButton.classList.remove("is-active");
  elements.adminModeButton.classList.add("is-active");
  setScreen("admin");
  await loadAdminData();
  renderAdmin();
}

async function refreshMe({ showLoginOnFailure = false, intendedMode = "recognize" } = {}) {
  try {
    const response = await getJson("/auth/me", { suppressErrorLog: true });
    state.adminUser = response.user;
    if (!csrfToken()) {
      // CSRF cookie missing: treat as not-logged-in. Only force the login
      // screen if the caller asked for it. Public kiosk boot does not.
      state.adminUser = null;
      if (showLoginOnFailure) {
        handleAuthRequired(SESSION_NOT_READY_MESSAGE, { intendedMode });
      }
      updateAuthUi();
      return false;
    }
  } catch (error) {
    state.adminUser = null;
    if (showLoginOnFailure) {
      handleAuthRequired(SESSION_NOT_READY_MESSAGE, { intendedMode });
      return false;
    }
  }
  updateAuthUi();
  return Boolean(state.adminUser);
}

async function loadAdminData() {
  elements.adminAlert.classList.add("is-hidden");
  try {
    const [metrics, persons, lecturers, users, classes, sessions, logs, devices] = await Promise.all([
      getJson("/admin/metrics"),
      getJson("/admin/persons"),
      getJson("/admin/lecturers"),
      getJson("/admin/users"),
      getJson("/admin/classes"),
      getJson("/admin/attendance-sessions?include_deleted=true"),
      getJson("/admin/attendance-logs"),
      getJson("/admin/devices/configs"),
    ]);
    state.adminData = { metrics, persons: persons.items, lecturers: lecturers.items, users: users.items, classes: classes.items, sessions: sessions.items, logs: logs.items, devices };
  } catch (error) {
    elements.adminAlert.textContent = errorSummaryFor(error, "Data admin gagal dimuat");
    elements.adminAlert.classList.remove("is-hidden");
  }
}

function adminRows(items, columns, actionsFor, options = {}) {
  if (!items?.length) {
    return `<div class="empty-state">${options.emptyText ?? "Belum ada data"}</div>`;
  }
  const actionWidth = options.actionWidth ?? "220px";
  return `
    <div class="data-table" style="--cols:${columns.map((column) => column.width || "1fr").join(" ")};--action-col:${actionWidth}">
      <div class="table-head">${columns.map((column) => `<span>${column.label}</span>`).join("")}<span>Aksi</span></div>
      ${items
        .map(
          (item, index) => `
            <article class="table-row ${item.is_active === false ? "is-inactive" : ""}">
              ${columns.map((column) => `<span data-label="${column.label}">${column.render(item, index)}</span>`).join("")}
              <span class="row-actions">${actionsFor(item)}</span>
            </article>
          `,
        )
        .join("")}
    </div>`;
}

function adminSelectOptions(items, valueKey, labelKey, selected = null) {
  return `<option value="">-</option>${(items || [])
    .map((item) => {
      const value = String(item[valueKey] ?? "");
      return `<option value="${escapeHtml(value)}" ${value === String(selected ?? "") ? "selected" : ""}>${escapeHtml(item[labelKey] ?? "")}</option>`;
    })
    .join("")}`;
}

function renderAdmin() {
  const titles = {
    dashboard: ["Dashboard", "Ringkasan Sistem"],
    students: ["Mahasiswa", "Data Mahasiswa"],
    lecturers: ["Dosen", "Data Dosen"],
    users: ["Akun Login", "Registrasi Admin dan Dosen"],
    classes: ["Kelas", "Manajemen Kelas"],
    enrollment: ["Enrollment", "Pendaftaran Wajah"],
    sessions: ["Sesi Absensi", "Manajemen Sesi"],
    logs: ["Log Absensi", "Riwayat Absensi"],
    devices: ["Perangkat", "Konfigurasi Perangkat"],
  };
  const [eyebrow, title] = titles[state.adminView] ?? titles.dashboard;
  elements.adminEyebrow.textContent = eyebrow;
  elements.adminTitle.textContent = title;
  document.querySelectorAll(".admin-nav").forEach((button) => button.classList.toggle("is-active", button.dataset.adminView === state.adminView));
  elements.adminPrimaryAction.classList.toggle("is-hidden", state.adminView === "dashboard" || state.adminView === "logs" || state.adminView === "enrollment" || state.adminView === "students");
  elements.adminPrimaryAction.textContent = state.adminView === "devices" ? "Tambah / Ubah Perangkat" : state.adminView === "users" ? "Tambah Akun" : "Tambah Data";
  const renderers = {
    dashboard: renderAdminDashboard,
    students: renderStudents,
    lecturers: renderLecturers,
    users: renderUsers,
    classes: renderClasses,
    enrollment: renderEnrollmentAdmin,
    sessions: renderSessions,
    logs: renderLogs,
    devices: renderDevices,
  };
  elements.adminBody.innerHTML = `${(renderers[state.adminView] ?? renderAdminDashboard)()}${renderAdminDrawer()}`;
  if (state.adminEdit?.type === "session") {
    loadSessionTodayLogs(state.adminEdit.item?.session_id);
  }
}

function renderAdminDashboard() {
  const metrics = state.adminData.metrics ?? {};
  const logs = state.adminData.logs ?? [];
  return `
    <section class="metric-grid">
      ${[
        ["Mahasiswa", metrics.total_students ?? 0],
        ["Dosen", metrics.total_lecturers ?? 0],
        ["Kelas", metrics.total_classes ?? 0],
        ["Enrollment", metrics.total_enrollments ?? 0],
        ["Hadir Hari Ini", metrics.today_attendance_count ?? 0],
        ["Gagal/Tidak Dikenal", metrics.unknown_failed_count ?? 0],
      ]
        .map(([label, value]) => `<article class="metric-card"><span>${label}</span><strong>${value}</strong></article>`)
        .join("")}
    </section>
    <h3>Absensi Terbaru</h3>
    ${adminRows(
      logs.slice(0, 8),
      [
        { label: "Nama", render: (item) => item.full_name ?? "-" },
        { label: "ID", render: (item) => item.student_id ?? "-" },
        { label: "Status", render: (item) => attendanceDecisionLabel(item.decision, item.reason) },
        { label: "Waktu", render: (item) => `${formatDateOnly(item.created_at)} ${formatTimeOnly(item.created_at)}` },
      ],
      () => "",
    )}
  `;
}

function renderStudents() {
  const persons = state.adminData.persons ?? [];
  return `<section class="admin-panel split-panel">
      <div>
        <strong>Mahasiswa adalah halaman pengelolaan data.</strong>
        <p>Tambah mahasiswa baru dilakukan melalui menu Enrollment. Perekaman wajah juga dimulai dari Enrollment.</p>
      </div>
      <button data-action="go-enrollment" type="button">Buka Enrollment</button>
    </section>${adminRows(
    persons,
    [
      { label: "No", width: "56px", render: (_item, index) => index + 1 },
      { label: "Foto", width: "72px", render: (item) => (item.sample_count ? `<img class="face-thumb" src="${API_BASE_URL}/admin/persons/${item.person_id}/photo" alt="" />` : `<span class="avatar-mini">?</span>`) },
      { label: "ID", width: "minmax(120px, 1.1fr)", render: (item) => item.student_id },
      { label: "Nama", width: "minmax(130px, 1.2fr)", render: (item) => item.full_name },
      { label: "Kelas", width: "minmax(70px, 0.7fr)", render: (item) => item.class_code ?? "-" },
      { label: "Status", width: "112px", render: (item) => activeStatus(item) },
      { label: "Enrollment", width: "150px", render: enrollmentStatus },
    ],
    (item) => `<button class="action-btn" data-action="edit-student" data-id="${item.person_id}" type="button">Edit</button><button class="action-btn" data-action="reenroll" data-id="${item.person_id}" type="button">Re-enroll</button><button class="action-btn danger" data-action="clear-face-data" data-id="${item.person_id}" type="button">Hapus Wajah</button>${item.is_active ? `<button class="action-btn danger" data-action="deactivate-student" data-id="${item.person_id}" type="button">Nonaktifkan</button>` : `<button class="action-btn success" data-action="reactivate-student" data-id="${item.person_id}" type="button">Aktifkan</button>`}<button class="action-btn danger" data-action="delete-student" data-id="${item.person_id}" type="button">Hapus</button>`,
    { emptyText: "Belum ada mahasiswa aktif", actionWidth: "150px" },
  )}`;
}

function studentForm(item = {}) {
  return `
    <form class="admin-form" data-form="student">
      <input type="hidden" name="person_id" value="${item.person_id ?? ""}" />
      <label>ID Mahasiswa<input name="student_id" value="${item.student_id ?? ""}" placeholder="otomatis jika kosong" /></label>
      <label>Nama<input name="full_name" value="${item.full_name ?? ""}" required /></label>
      <label>Email<input name="email" value="${item.email ?? ""}" /></label>
      <label>Kelas<select name="class_id">${adminSelectOptions(state.adminData.classes, "class_id", "class_code", item.class_id)}</select></label>
      <button type="submit">Simpan</button><button class="secondary" data-action="cancel-edit" type="button">Batal</button>
    </form>`;
}

function renderLecturers() {
  return `${lecturerForm()}${adminRows(
    state.adminData.lecturers ?? [],
    [
      { label: "Kode", render: (item) => item.lecturer_code },
      { label: "Nama", render: (item) => item.full_name },
      { label: "Email", render: (item) => item.email ?? "-" },
      { label: "Departemen", render: (item) => item.department ?? "-" },
      { label: "Status", render: (item) => activeStatus(item) },
    ],
    (item) => `<button class="action-btn" data-action="edit-lecturer" data-id="${item.lecturer_id}" type="button">Edit</button>${item.is_active ? `<button class="action-btn danger" data-action="deactivate-lecturer" data-id="${item.lecturer_id}" type="button">Nonaktifkan</button>` : `<button class="action-btn success" data-action="reactivate-lecturer" data-id="${item.lecturer_id}" type="button">Aktifkan</button>`}`,
  )}`;
}

function lecturerForm(item = {}) {
  const codeField = item.lecturer_id
    ? `<label>Kode Dosen<input name="lecturer_code" value="${escapeHtml(item.lecturer_code ?? "")}" /></label>`
    : `<label>Kode Dosen <span class="field-hint">otomatis jika kosong</span><input name="lecturer_code" placeholder="DSN-0001 (otomatis)" /></label>`;
  return `<form class="admin-form" data-form="lecturer"><input type="hidden" name="lecturer_id" value="${item.lecturer_id ?? ""}" />${codeField}<label>Nama<input name="full_name" value="${escapeHtml(item.full_name ?? "")}" required /></label><label>Email<input name="email" value="${escapeHtml(item.email ?? "")}" /></label><label>Departemen<input name="department" value="${escapeHtml(item.department ?? "")}" /></label><button type="submit">${item.lecturer_id ? "Simpan" : "Tambah Dosen"}</button>${item.lecturer_id ? `<button class="secondary" data-action="cancel-edit" type="button">Batal</button>` : ""}</form>`;
}

function roleLabel(role) {
  if (role === "admin") return "Admin";
  if (role === "lecturer") return "Dosen";
  return role || "-";
}

function renderUsers() {
  return `${userForm()}${adminRows(
    state.adminData.users ?? [],
    [
      { label: "Username", width: "minmax(120px, 1fr)", render: (item) => escapeHtml(item.username) },
      { label: "Nama", width: "minmax(140px, 1.1fr)", render: (item) => escapeHtml(item.full_name) },
      { label: "Role", width: "100px", render: (item) => roleLabel(item.role) },
      { label: "Dosen", width: "minmax(120px, 1fr)", render: (item) => escapeHtml(item.lecturer_name ?? "-") },
      { label: "Email", width: "minmax(130px, 1fr)", render: (item) => escapeHtml(item.email ?? "-") },
      { label: "Status", width: "112px", render: (item) => activeStatus(item) },
    ],
    (item) => `<button class="action-btn" data-action="edit-user" data-id="${item.admin_id}" type="button">Edit</button>${item.is_active ? `<button class="action-btn danger" data-action="deactivate-user" data-id="${item.admin_id}" type="button">Nonaktifkan</button>` : `<button class="action-btn success" data-action="reactivate-user" data-id="${item.admin_id}" type="button">Aktifkan</button>`}`,
    { actionWidth: "150px" },
  )}`;
}

function userForm(item = {}) {
  const role = item.role ?? "admin";
  const lecturerOptions = adminSelectOptions(state.adminData.lecturers, "lecturer_id", "full_name", item.lecturer_id);
  const passwordLabel = item.admin_id ? "Password baru" : "Password";
  const passwordAttrs = item.admin_id ? `placeholder="Kosongkan jika tidak diganti"` : "required";
  return `<form class="admin-form" data-form="user">
    <input type="hidden" name="admin_id" value="${item.admin_id ?? ""}" />
    <label>Username<input name="username" value="${escapeHtml(item.username ?? "")}" autocomplete="off" required /></label>
    <label>Nama<input name="full_name" value="${escapeHtml(item.full_name ?? "")}" required /></label>
    <label>Email<input name="email" value="${escapeHtml(item.email ?? "")}" /></label>
    <label>${passwordLabel}<input name="password" type="password" autocomplete="new-password" ${passwordAttrs} /></label>
    <label>Role<select name="role"><option value="admin" ${role === "admin" ? "selected" : ""}>Admin</option><option value="lecturer" ${role === "lecturer" ? "selected" : ""}>Dosen</option></select></label>
    <label>Dosen<select name="lecturer_id">${lecturerOptions}</select></label>
    <button type="submit">${item.admin_id ? "Simpan" : "Tambah Akun"}</button>${item.admin_id ? `<button class="secondary" data-action="cancel-edit" type="button">Batal</button>` : ""}
  </form>`;
}

function renderClasses() {
  return `${classForm()}${adminRows(
    state.adminData.classes ?? [],
    [
      { label: "Kode", render: (item) => item.class_code },
      { label: "Nama", render: (item) => item.class_name },
      { label: "Dosen", render: (item) => item.lecturer_name ?? "-" },
      { label: "Mahasiswa", render: (item) => item.total_students ?? 0 },
      { label: "Status", render: (item) => activeStatus(item) },
    ],
    (item) => `<button class="action-btn" data-action="edit-class" data-id="${item.class_id}" type="button">Edit</button>${item.is_active ? `<button class="action-btn danger" data-action="deactivate-class" data-id="${item.class_id}" type="button">Nonaktifkan</button>` : `<button class="action-btn success" data-action="reactivate-class" data-id="${item.class_id}" type="button">Aktifkan</button>`}`,
  )}`;
}

function classForm(item = {}) {
  const codeField = item.class_id
    ? `<label>Kode Kelas<input name="class_code" value="${escapeHtml(item.class_code ?? "")}" /></label>`
    : `<label>Kode Kelas <span class="field-hint">otomatis jika kosong</span><input name="class_code" placeholder="KLS-0001 (otomatis)" /></label>`;
  return `<form class="admin-form" data-form="class"><input type="hidden" name="class_id" value="${item.class_id ?? ""}" />${codeField}<label>Nama Kelas<input name="class_name" value="${escapeHtml(item.class_name ?? "")}" required /></label><label>Dosen<select name="lecturer_id">${adminSelectOptions(state.adminData.lecturers, "lecturer_id", "full_name", item.lecturer_id)}</select></label><label>Deskripsi<input name="description" value="${escapeHtml(item.description ?? "")}" /></label><button type="submit">${item.class_id ? "Simpan" : "Tambah Kelas"}</button>${item.class_id ? `<button class="secondary" data-action="cancel-edit" type="button">Batal</button>` : ""}</form>`;
}

function renderEnrollmentAdmin() {
  const persons = state.adminData.persons ?? [];
  return `<section class="admin-panel enrollment-admin-panel">
      <div>
        <p class="eyebrow">Registrasi</p>
        <h3>Enrollment mahasiswa dan wajah</h3>
        <p>Gunakan halaman ini untuk membuat data mahasiswa baru, memilih kelas, lalu merekam wajah. Re-enrollment dan pencabutan data wajah juga dilakukan di sini.</p>
      </div>
      <button id="admin-start-enrollment" type="button">Mulai Pendaftaran Wajah</button>
    </section>${adminRows(
      persons,
      [
        { label: "ID", render: (item) => item.student_id },
        { label: "Nama", render: (item) => item.full_name },
        { label: "Kelas", render: (item) => item.class_code ?? "-" },
        { label: "Status Data", render: (item) => activeStatus(item) },
        { label: "Status Wajah", render: enrollmentStatus },
      ],
      (item) => `<button class="action-btn" data-action="reenroll" data-id="${item.person_id}" type="button">Re-enroll</button><button class="action-btn danger" data-action="clear-face-data" data-id="${item.person_id}" type="button">Hapus Wajah</button>`,
      { emptyText: "Belum ada enrollment", actionWidth: "240px" },
    )}`;
}

function renderSessions() {
  const sessions = (state.adminData.sessions ?? []).filter(sessionMatchesAdminFilters);
  const activeSessions = (state.adminData.sessions ?? []).filter((item) => !item.is_deleted && sessionIsCurrentlyUsable(item));
  const activeSummary = activeSessions.length
    ? activeSessions.map((session) => `${escapeHtml(session.session_name)} (${escapeHtml(session.session_code)})`).join(", ")
    : "Belum ada sesi absensi aktif";
  return `<section class="admin-panel split-panel">
      <div>
        <strong>Sesi absensi aktif</strong>
        <p>${activeSummary}</p>
      </div>
      <span>${activeSessions.length} aktif</span>
    </section>${sessionFilterForm()}${sessionForm()}${adminRows(
    sessions,
    [
      { label: "Kode", width: "minmax(128px, 1fr)", render: (item) => item.session_code },
      { label: "Nama", width: "minmax(130px, 1.1fr)", render: (item) => item.session_name },
      { label: "Kelas", width: "minmax(96px, 0.8fr)", render: (item) => item.class_name ?? item.class_code ?? "-" },
      { label: "Dosen", width: "minmax(120px, 1fr)", render: (item) => item.lecturer_name ?? "-" },
      { label: "Status", width: "120px", render: sessionStatus },
      { label: "Hari", width: "minmax(140px, 1fr)", render: (item) => formatRepeatDays(item.repeat_days) },
      { label: "Jam", width: "minmax(100px, 0.8fr)", render: (item) => formatSessionTimeRange(item.start_time, item.end_time) },
    ],
    (item) =>
      `<button class="action-btn" data-action="copy-session-code" data-code="${escapeHtml(item.session_code)}" type="button">Salin Kode</button><button class="action-btn" data-action="edit-session" data-id="${item.session_id}" type="button">Detail</button>${
        item.is_deleted
          ? ""
          : item.is_active
            ? `<button class="action-btn danger" data-action="deactivate-session" data-id="${item.session_id}" type="button">Nonaktifkan</button>`
            : `<button class="action-btn success" data-action="activate-session" data-id="${item.session_id}" type="button">Aktifkan</button>`
      }${item.is_deleted ? "" : `<button class="action-btn danger" data-action="delete-session" data-id="${item.session_id}" type="button">Hapus</button>`}`,
    { emptyText: "Belum ada sesi absensi", actionWidth: "150px" },
  )}`;
}

function sessionForm(item = {}) {
  const codeField = item.session_id
    ? `<label>Kode Sesi<input name="session_code" value="${escapeHtml(item.session_code ?? "")}" required /></label>`
    : "";
  const selectedKind = item.session_kind === "class" ? "lecture" : (item.session_kind ?? "lecture");
  const kindOptions = [
    ["lecture", "Kuliah"],
    ["lab", "Praktikum"],
    ["exam", "Ujian"],
    ["other", "Lainnya"],
  ]
    .map(([value, label]) => `<option value="${value}" ${selectedKind === value ? "selected" : ""}>${label}</option>`)
    .join("");
  const days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
  const dayLabels = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
  const repeatDays = Array.isArray(item.repeat_days) ? item.repeat_days : [];
  const dayCheckboxes = days
    .map((day, i) => `<label class="checkbox-label"><input type="checkbox" name="repeat_days" value="${day}" ${repeatDays.includes(day) ? "checked" : ""} /> ${dayLabels[i]}</label>`)
    .join("");
  const startTimeVal = item.start_time ? String(item.start_time).substring(0, 5) : "";
  const endTimeVal = item.end_time ? String(item.end_time).substring(0, 5) : "";
  return `<form class="admin-form" data-form="session"><input type="hidden" name="session_id" value="${item.session_id ?? ""}" />${codeField}<label>Nama Sesi<input name="session_name" value="${escapeHtml(item.session_name ?? "")}" placeholder="Absensi Pagi" required /></label><label>Jenis<select name="session_kind">${kindOptions}</select></label><label>Kelas<select name="class_id">${adminSelectOptions(state.adminData.classes, "class_id", "class_code", item.class_id)}</select></label><label>Dosen<select name="lecturer_id">${adminSelectOptions(state.adminData.lecturers, "lecturer_id", "full_name", item.lecturer_id)}</select></label><label>Device<input name="device_code" value="${escapeHtml(item.device_code ?? DEVICE_CODE)}" /></label><fieldset class="admin-fieldset"><legend>Hari Aktif</legend><div class="day-checkboxes">${dayCheckboxes}</div></fieldset><label>Jam Mulai<input name="start_time" type="time" value="${startTimeVal}" /></label><label>Jam Selesai<input name="end_time" type="time" value="${endTimeVal}" /></label><button type="submit">${item.session_id ? "Simpan" : "Tambah Sesi"}</button>${item.session_id ? `<button class="secondary" data-action="cancel-edit" type="button">Batal</button>` : ""}</form>`;
}

function sessionFilterForm() {
  const filters = state.adminSessionFilters;
  return `<form class="admin-form admin-filter-form" data-form="session-filter">
    <label>Kelas<select name="class_id">${adminSelectOptions(state.adminData.classes, "class_id", "class_code", filters.class_id)}</select></label>
    <label>Tanggal<input name="date" type="date" value="${escapeHtml(filters.date)}" /></label>
    <label>Status<select name="status">
      <option value="" ${filters.status ? "" : "selected"}>Semua</option>
      <option value="active" ${filters.status === "active" ? "selected" : ""}>Aktif</option>
      <option value="inactive" ${filters.status === "inactive" ? "selected" : ""}>Nonaktif</option>
      <option value="deleted" ${filters.status === "deleted" ? "selected" : ""}>Diarsipkan</option>
    </select></label>
    <label class="checkbox-label"><input name="include_deleted" type="checkbox" ${filters.include_deleted ? "checked" : ""} /> Tampilkan sesi dihapus</label>
    <button type="submit">Filter</button>
  </form>`;
}

function renderLogs() {
  return adminRows(
    state.adminData.logs ?? [],
    [
      { label: "No", width: "52px", render: (item) => item.no },
      { label: "Foto", width: "70px", render: (item) => (item.captured_image_url ? `<img class="face-thumb" src="${API_BASE_URL}${item.captured_image_url}" alt="" />` : `<span class="avatar-mini">?</span>`) },
      { label: "ID", render: (item) => item.student_id ?? "-" },
      { label: "Nama", render: (item) => item.full_name ?? "-" },
      { label: "Kelas", render: (item) => item.class_code ?? "-" },
      { label: "Tanggal", render: (item) => formatDateOnly(item.created_at) },
      { label: "Jam", render: (item) => formatTimeOnly(item.created_at) },
      { label: "Status", render: (item) => attendanceDecisionLabel(item.decision, item.reason) },
      { label: "Cocok", render: (item) => formatPercent(item.confidence) },
    ],
    (item) => `<button class="action-btn" data-action="mark-log" data-id="${item.log_id}" type="button">Edit</button><button class="action-btn danger" data-action="deactivate-log" data-id="${item.log_id}" type="button">Sembunyikan</button>`,
  );
}

function renderDevices() {
  return `${deviceForm()}${adminRows(
    state.adminData.devices ?? [],
    [
      { label: "Kamera", width: "96px", render: () => cameraStatusDot() },
      { label: "Kode", render: (item) => item.device_code },
      { label: "Nama", render: (item) => item.device_name },
      { label: "Lokasi", render: (item) => item.location_hint ?? "-" },
      { label: "API", render: (item) => item.is_enabled ? statusBadge("Aktif", "success") : statusBadge("Nonaktif", "danger") },
      { label: "Terakhir", render: (item) => item.heartbeat?.captured_at ? `${formatDateOnly(item.heartbeat.captured_at)} ${formatTimeOnly(item.heartbeat.captured_at)}` : "-" },
    ],
    (item) => `<button class="action-btn" data-action="edit-device" data-id="${item.device_code}" type="button">Edit</button>`,
  )}`;
}

function deviceForm(item = {}) {
  const selectedCameraOption = state.cameraSelectionMode === "manual" ? state.selectedCameraId : "";
  const cameraOptions = [
    `<option value="" ${selectedCameraOption ? "" : "selected"}>Kamera depan/default</option>`,
    ...state.cameraDevices.map(
      (device, index) =>
        `<option value="${device.deviceId}" ${device.deviceId === selectedCameraOption ? "selected" : ""}>${escapeHtml(cameraLabel(device, index))}</option>`,
    ),
  ].join("");
  return `<form class="admin-form device-config-form" data-form="device"><label>Kode Device<input name="device_code" value="${item.device_code ?? DEVICE_CODE}" required /></label><label>Nama<input name="device_name" value="${item.device_name ?? "Web Kiosk"}" required /></label><label>Lokasi<input name="location_hint" value="${item.location_hint ?? ""}" /></label><label>Pilih kamera<select name="camera_device_id">${cameraOptions}</select></label><label>Similarity<input name="similarity_threshold" type="number" step="0.01" value="${item.similarity_threshold ?? 0.45}" /></label><label>Margin<input name="candidate_margin_threshold" type="number" step="0.01" value="${item.candidate_margin_threshold ?? 0.05}" /></label><label>Liveness<input name="liveness_threshold" type="number" step="0.01" value="${item.liveness_threshold ?? 0.7}" /></label><label>Accepted/pose<input name="accepted_per_pose" type="number" value="${item.accepted_per_pose ?? 3}" /></label><button type="submit">Gunakan kamera ini</button><button class="secondary" data-action="refresh-cameras" type="button">Periksa Kamera</button></form><section class="admin-panel camera-summary">${cameraStatusDot()}<span>${cameraStatusText()}</span>${state.cameraWarning ? `<small>${escapeHtml(state.cameraWarning)}</small>` : ""}</section>`;
}

function cameraStatusText() {
  if (state.cameraStatus === "connected") return "Kamera tersambung";
  if (state.cameraStatus === "disconnected") return "Kamera tidak tersambung";
  return "Memeriksa kamera...";
}

function renderAdminDrawer() {
  if (!state.adminEdit) return "";
  const { type, item } = state.adminEdit;
  const forms = {
    student: studentForm(item),
    user: userForm(item),
    lecturer: lecturerForm(item),
    class: classForm(item),
    session: sessionForm(item),
    device: deviceForm(item),
  };
  const titles = {
    student: "Edit Mahasiswa",
    user: "Edit Akun Login",
    lecturer: "Edit Dosen",
    class: "Edit Kelas",
    session: "Edit Sesi Absensi",
    device: "Edit Perangkat",
  };
  return `<aside class="admin-drawer" aria-label="${titles[type] ?? "Edit"}">
    <div class="drawer-head">
      <div>
        <p class="eyebrow">Detail</p>
        <h3>${titles[type] ?? "Edit Data"}</h3>
      </div>
      <button class="secondary compact" data-action="cancel-edit" type="button">Batal</button>
    </div>
    ${type === "student" ? studentDetailSummary(item) : ""}
    ${type === "session" ? sessionDetailSummary(item) : ""}
    ${forms[type] ?? ""}
  </aside>`;
}

function studentDetailSummary(item = {}) {
  return `<section class="detail-summary">
    <div>${item.sample_count ? `<img class="face-thumb large" src="${API_BASE_URL}/admin/persons/${item.person_id}/photo" alt="" />` : `<span class="avatar-mini large">?</span>`}</div>
    <dl>
      <div><dt>ID</dt><dd>${escapeHtml(item.student_id ?? "-")}</dd></div>
      <div><dt>Status</dt><dd>${activeStatus(item)}</dd></div>
      <div><dt>Enrollment</dt><dd>${enrollmentStatus(item)}</dd></div>
      <div><dt>Dibuat</dt><dd>${formatDateOnly(item.created_at)}</dd></div>
      <div><dt>Diperbarui</dt><dd>${formatDateOnly(item.updated_at)}</dd></div>
    </dl>
  </section>`;
}

function sessionDetailSummary(item = {}) {
  return `<section class="detail-summary session-detail-summary">
    <dl>
      <div><dt>Kode</dt><dd>${escapeHtml(item.session_code ?? "-")}</dd></div>
      <div><dt>Status</dt><dd>${activeStatus(item)}</dd></div>
      <div><dt>Kelas</dt><dd>${escapeHtml(item.class_name ?? item.class_code ?? "-")}</dd></div>
      <div><dt>Dosen</dt><dd>${escapeHtml(item.lecturer_name ?? "-")}</dd></div>
      <div><dt>Hari</dt><dd>${formatRepeatDays(item.repeat_days)}</dd></div>
      <div><dt>Jam</dt><dd>${formatSessionTimeRange(item.start_time, item.end_time)}</dd></div>
    </dl>
    <details class="session-today-logs">
      <summary>Absensi Hari Ini</summary>
      <div id="session-today-logs-container" data-session-id="${item.session_id ?? ""}"></div>
    </details>
  </section>`;
}

function cameraStatusDot() {
  const tone = state.cameraStatus === "connected" ? "green" : state.cameraStatus === "disconnected" ? "red" : "yellow";
  return `<span class="status-dot ${tone}" title="${cameraStatusText()}"></span>`;
}

function formObject(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function nullable(value) {
  const text = String(value ?? "").trim();
  return text ? text : null;
}

async function handleAdminForm(event) {
  const form = event.target.closest("form[data-form]");
  if (!form) return;
  event.preventDefault();
  const data = formObject(form);
  try {
    if (form.dataset.form === "session-filter") {
      state.adminSessionFilters = {
        class_id: nullable(data.class_id) ?? "",
        date: nullable(data.date) ?? "",
        status: nullable(data.status) ?? "",
        include_deleted: Boolean(data.include_deleted),
      };
      renderAdmin();
      return;
    }
    if (form.dataset.form === "student") {
      let studentId = nullable(data.student_id);
      if (!studentId) {
        const classItem = (state.adminData.classes ?? []).find((item) => item.class_id === data.class_id);
        studentId = (await getJson(`/admin/ids/next?entity=student&class_code=${encodeURIComponent(classItem?.class_code ?? "AUTO")}`)).id;
      }
      const payload = { student_id: studentId, full_name: data.full_name, email: nullable(data.email), class_id: nullable(data.class_id), is_active: false };
      if (data.person_id) await apiJson("PUT", `/admin/persons/${data.person_id}`, payload);
      else await apiJson("POST", "/admin/persons", payload);
    }
    if (form.dataset.form === "user") {
      const payload = {
        username: data.username,
        full_name: data.full_name,
        email: nullable(data.email),
        role: data.role || "admin",
        lecturer_id: data.role === "lecturer" ? nullable(data.lecturer_id) : null,
        is_active: true,
      };
      if (data.password) {
        payload.password = data.password;
      }
      if (data.admin_id) await apiJson("PUT", `/admin/users/${data.admin_id}`, payload);
      else await apiJson("POST", "/admin/users", payload);
    }
    if (form.dataset.form === "lecturer") {
      const payload = { lecturer_code: data.lecturer_code, full_name: data.full_name, email: nullable(data.email), department: nullable(data.department), is_active: true };
      if (data.lecturer_id) await apiJson("PUT", `/admin/lecturers/${data.lecturer_id}`, payload);
      else await apiJson("POST", "/admin/lecturers", payload);
    }
    if (form.dataset.form === "class") {
      const payload = { class_code: data.class_code, class_name: data.class_name, lecturer_id: nullable(data.lecturer_id), description: nullable(data.description), is_active: true };
      if (data.class_id) await apiJson("PUT", `/admin/classes/${data.class_id}`, payload);
      else await apiJson("POST", "/admin/classes", payload);
    }
    if (form.dataset.form === "session") {
      const repeatDaysChecked = Array.from(form.querySelectorAll('input[name="repeat_days"]:checked')).map((cb) => cb.value);
      const payload = {
        session_name: data.session_name,
        session_kind: data.session_kind || "lecture",
        class_id: nullable(data.class_id),
        lecturer_id: nullable(data.lecturer_id),
        device_code: nullable(data.device_code),
        cooldown_seconds: 30,
        repeat_days: repeatDaysChecked.length > 0 ? repeatDaysChecked : null,
        start_time: nullable(data.start_time) || null,
        end_time: nullable(data.end_time) || null,
        timezone: "Asia/Makassar",
        is_active: true,
      };
      if (nullable(data.session_code)) {
        payload.session_code = nullable(data.session_code);
      }
      if (data.session_id) await apiJson("PUT", `/admin/attendance-sessions/${data.session_id}`, payload);
      else await apiJson("POST", "/admin/attendance-sessions", payload);
    }
    if (form.dataset.form === "device") {
      const cameraDeviceId = nullable(data.camera_device_id) ?? "";
      storeCameraId(cameraDeviceId, { manual: Boolean(cameraDeviceId) });
      const payload = {
        device_name: data.device_name,
        location_hint: nullable(data.location_hint),
        det_thresh: 0.6,
        det_size: [320, 320],
        max_faces: 1,
        min_face_width_px: 160,
        min_brightness: 75,
        min_blur_score: 90,
        similarity_threshold: Number(data.similarity_threshold || 0.45),
        candidate_margin_threshold: Number(data.candidate_margin_threshold || 0.05),
        liveness_threshold: Number(data.liveness_threshold || 0.7),
        multi_frame_confirm: 2,
        accepted_per_pose: Number(data.accepted_per_pose || 3),
        cooldown_seconds: 30,
        is_enabled: true,
      };
      await apiJson("PUT", `/admin/devices/config/${encodeURIComponent(data.device_code)}`, payload);
      await restartCamera();
    }
    state.adminEdit = null;
    await loadAdminData();
    renderAdmin();
  } catch (error) {
    elements.adminAlert.textContent = errorSummaryFor(error, "Data gagal disimpan");
    elements.adminAlert.classList.remove("is-hidden");
  }
}

async function handleAdminAction(event) {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const { action, id } = button.dataset;
  let successMessage = "";
  try {
    if (action === "cancel-edit") {
      state.adminEdit = null;
      renderAdmin();
      return;
    }
    if (action === "go-enrollment") {
      state.adminView = "enrollment";
      renderAdmin();
      return;
    }
    if (action === "refresh-cameras") {
      event.preventDefault();
      await enumerateCameras();
      renderAdmin();
      return;
    }
    if (action === "copy-session-code") {
      const code = button.dataset.code ?? "";
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(code);
      } else {
        window.prompt("Salin kode sesi", code);
      }
      elements.adminAlert.textContent = "Kode sesi berhasil disalin.";
      elements.adminAlert.classList.remove("is-hidden");
      return;
    }
    if (action === "edit-student") {
      state.adminEdit = { type: "student", item: (state.adminData.persons ?? []).find((item) => item.person_id === id) };
      renderAdmin();
      return;
    }
    if (action === "edit-user") {
      state.adminEdit = { type: "user", item: (state.adminData.users ?? []).find((item) => item.admin_id === id) };
      renderAdmin();
      return;
    }
    if (action === "edit-lecturer") {
      state.adminEdit = { type: "lecturer", item: (state.adminData.lecturers ?? []).find((item) => item.lecturer_id === id) };
      renderAdmin();
      return;
    }
    if (action === "edit-class") {
      state.adminEdit = { type: "class", item: (state.adminData.classes ?? []).find((item) => item.class_id === id) };
      renderAdmin();
      return;
    }
    if (action === "edit-session") {
      state.adminEdit = { type: "session", item: (state.adminData.sessions ?? []).find((item) => item.session_id === id) };
      renderAdmin();
      return;
    }
    if (action === "edit-device") {
      state.adminEdit = { type: "device", item: (state.adminData.devices ?? []).find((item) => item.device_code === id) };
      renderAdmin();
      return;
    }
    if (action === "reenroll") {
      const person = (state.adminData.persons ?? []).find((item) => item.person_id === id);
      setMode("enroll");
      showIdentityModal();
      document.getElementById("student-id").value = person.student_id;
      document.getElementById("full-name").value = person.full_name;
      document.getElementById("email").value = person.email ?? "";
      populateIdentityClassOptions(person.class_id ?? "");
    }
    if (action === "clear-face-data") {
      const person = (state.adminData.persons ?? []).find((item) => item.person_id === id);
      const label = person ? `${person.full_name} (${person.student_id})` : "mahasiswa ini";
      const confirmed = window.confirm(`Hapus wajah untuk ${label}? Data mahasiswa tetap ada, tetapi template dan foto wajah tidak digunakan lagi sampai re-enroll.`);
      if (!confirmed) return;
      const result = await apiJson("DELETE", `/admin/persons/${id}/face-data`);
      successMessage = result.detail || "Data wajah berhasil dihapus.";
    }
    if (action === "deactivate-student") await apiJson("PATCH", `/admin/persons/${id}/deactivate`);
    if (action === "reactivate-student") await apiJson("PATCH", `/admin/persons/${id}/reactivate`);
    if (action === "deactivate-user") await apiJson("PATCH", `/admin/users/${id}/deactivate`);
    if (action === "reactivate-user") await apiJson("PATCH", `/admin/users/${id}/reactivate`);
    if (action === "delete-student") {
      const person = (state.adminData.persons ?? []).find((item) => item.person_id === id);
      const label = person ? `${person.full_name} (${person.student_id})` : "mahasiswa ini";
      if (!window.confirm(`Hapus ${label} dari daftar aktif? Riwayat absensi tetap disimpan, dan template wajah aktif akan dinonaktifkan.`)) return;
      const result = await apiJson("DELETE", `/admin/persons/${id}`);
      successMessage = result.detail || "Mahasiswa berhasil dihapus.";
    }
    if (action === "deactivate-lecturer") await apiJson("PATCH", `/admin/lecturers/${id}/deactivate`);
    if (action === "reactivate-lecturer") await apiJson("PATCH", `/admin/lecturers/${id}/reactivate`);
    if (action === "deactivate-class") await apiJson("PATCH", `/admin/classes/${id}/deactivate`);
    if (action === "reactivate-class") await apiJson("PATCH", `/admin/classes/${id}/reactivate`);
    if (action === "activate-session") await apiJson("PATCH", `/admin/attendance-sessions/${id}/activate`);
    if (action === "deactivate-session") await apiJson("PATCH", `/admin/attendance-sessions/${id}/deactivate`);
    if (action === "close-session") await apiJson("PATCH", `/admin/attendance-sessions/${id}/close`);
    if (action === "delete-session") {
      if (!window.confirm("Hapus sesi ini? Riwayat absensi tidak akan hilang, tetapi sesi tidak bisa digunakan lagi.")) return;
      const result = await apiJson("DELETE", `/admin/attendance-sessions/${id}`);
      successMessage = result.detail || "Sesi absensi berhasil dihapus.";
    }
    if (action === "deactivate-log") await apiJson("PATCH", `/admin/attendance-logs/${id}/deactivate`);
    if (action === "mark-log") await apiJson("PATCH", `/admin/attendance-logs/${id}`, { decision: "manual_approved", reason: "admin_updated" });
    if (action !== "reenroll") {
      await loadAdminData();
      renderAdmin();
      if (successMessage) {
        elements.adminAlert.textContent = successMessage;
        elements.adminAlert.classList.remove("is-hidden");
      }
    }
  } catch (error) {
    elements.adminAlert.textContent = errorSummaryFor(error, "Aksi gagal");
    elements.adminAlert.classList.remove("is-hidden");
  }
}

function renderWizard() {
  if (state.mode === "recognize") {
    renderAttendance();
    return;
  }
  const pose = currentPose() ?? "front";
  const progress = poseProgress(pose);
  const guidance = guidanceFromResponse(state.lastFrameResponse);
  const tone = guideToneFor(state.lastFrameResponse);
  const resp = state.lastFrameResponse;
  const holding = Boolean(state.stableSince && !state.requestInFlight && !allPosesComplete());
  const stuckAdjust = resp?.capture_status === "stuck_adjust";
  const primaryInstruction = holding ? "Tahan..." : (stuckAdjust ? (resp?.ui_hint || "Arah wajah belum sesuai.") : guidance.instruction);

  // Top bar
  if (elements.enrollStudentName) {
    const name = state.personId ? (state.lastFrameResponse?.student_id || "") : "";
    elements.enrollStudentName.textContent = name || "";
  }

  // Single instruction line below oval
  if (elements.enrollInstruction) {
    elements.enrollInstruction.textContent = primaryInstruction;
  }

  // Oval-center text — only during holding/capturing
  if (holding || state.requestInFlight) {
    if (elements.ovalPrimary) elements.ovalPrimary.textContent = state.requestInFlight ? "Merekam..." : "Tahan...";
    if (elements.ovalSecondary) elements.ovalSecondary.textContent = progress.complete ? "Selesai" : `${progress.accepted + 1}/${state.acceptedPerPose || 1}`;
  } else if (resp?.accepted) {
    if (elements.ovalPrimary) elements.ovalPrimary.textContent = "Berhasil";
    if (elements.ovalSecondary) elements.ovalSecondary.textContent = resp.next_pose ? "Lanjut pose berikutnya" : "Semua pose selesai";
  } else {
    if (elements.ovalPrimary) elements.ovalPrimary.textContent = "";
    if (elements.ovalSecondary) elements.ovalSecondary.textContent = "";
  }

  // Guide tone
  elements.cameraStage.dataset.guideTone = tone;
  elements.cameraStage.dataset.flowState = state.requestInFlight ? "capturing" : holding ? "holding" : state.enrollmentState;

  // Cancel button
  elements.cancelButton.disabled =
    state.enrollmentState === "finishing" ||
    state.enrollmentState === "complete" ||
    (!state.enrollmentSessionId && state.enrollmentState !== "error");

  // Manual buttons
  elements.captureButton.disabled = !state.enrollmentSessionId || state.requestInFlight || !pose || allPosesComplete();
  elements.finishButton.disabled = !state.enrollmentSessionId || !allPosesComplete() || state.enrollmentState === "finishing";

  // Arrows
  activateArrow(guidance.arrow);

  // Guide geometry
  renderGuideGeometry(state.lastFrameResponse);

  // Pose dots
  renderPoseDots();

  // Status dot
  setStatusBadge(state.requestInFlight ? "capturing" : state.captureStatus);

  // Bottom sheet for warnings
  if (elements.enrollBottomSheet && elements.enrollWarning) {
    const showWarning = stuckAdjust || (resp && !resp.accepted && !holding && !state.requestInFlight);
    elements.enrollBottomSheet.classList.toggle("is-hidden", !showWarning);
    if (showWarning) {
      const reason = resp?.reason ? (QUALITY_GUIDANCE_COPY[normalizeQualityReason(resp.reason)] || resp.ui_hint || "") : "";
      elements.enrollWarning.textContent = reason;
    }
  }
}

function readIdentityForm() {
  const formData = new FormData(elements.startForm);
  return {
    student_id: String(formData.get("student_id") ?? "").trim(),
    full_name: String(formData.get("full_name") ?? "").trim(),
    email: String(formData.get("email") ?? "").trim() || null,
    class_id: String(formData.get("class_id") ?? "").trim() || null,
    device_code: DEVICE_CODE,
  };
}

class ApiError extends Error {
  constructor(message, options = {}) {
    super(message);
    this.name = "ApiError";
    this.status = options.status ?? null;
    this.url = options.url ?? null;
    this.body = options.body ?? null;
    this.cause = options.cause ?? null;
    this.retryAfterMs = options.retryAfterMs ?? null;
  }
}

function authFailureError(error) {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}

function detailMessage(body) {
  const detail = body?.detail ?? body;
  if (!detail) {
    return null;
  }
  if (typeof detail === "string") {
    return detail;
  }
  if (typeof detail.message === "string") {
    return detail.message;
  }
  if (typeof detail.code === "string") {
    return detail.code;
  }
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg ?? item.message ?? JSON.stringify(item)).join("; ");
  }
  return JSON.stringify(detail);
}

function errorSummary(error) {
  if (error instanceof ApiError) {
    if (error.status) {
      if (error.status >= 500) {
        return "Terjadi kesalahan saat menyimpan wajah";
      }
      if (error.status === 422 || error.status === 400) {
        return "Data pendaftaran belum valid";
      }
      if (error.status === 404) {
        return "Data perangkat tidak ditemukan";
      }
      return `${error.message} (HTTP ${error.status})`;
    }
    return error.message;
  }
  return "Pendaftaran gagal, coba ulangi";
}

function errorSummaryFor(error, fallback) {
  if (error instanceof ApiError) {
    if (!error.status) {
      return error.message || "API tidak dapat dihubungi";
    }
    return error.message || fallback;
  }
  return fallback;
}

function attendanceErrorSummary(error) {
  if (error instanceof ApiError) {
    if (!error.status) {
      return "API tidak dapat dihubungi";
    }
    if (error.status === 404) {
      return "Sesi absensi sudah tidak aktif";
    }
    if (error.status === 422 || error.status === 400) {
      return error.message || "Data absensi belum valid";
    }
    if (error.status >= 500) {
      return "Absensi gagal";
    }
  }
  return errorSummaryFor(error, "Gagal mengenali wajah");
}

function serverErrorMessageFor(path) {
  if (path.startsWith("/attendance")) {
    return "Absensi gagal";
  }
  if (path.startsWith("/recognize")) {
    return "Gagal mengenali wajah";
  }
  return "Terjadi kesalahan saat menyimpan wajah";
}

async function readResponseBody(response) {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function getJson(path, { suppressErrorLog = false } = {}) {
  const url = `${API_BASE_URL}${path}`;
  let response;
  try {
    response = await fetch(url, { credentials: "include" });
  } catch (error) {
    console.error("Network request failed", { url, error });
    throw new ApiError("API tidak dapat dihubungi", { url, cause: error });
  }

  const body = await readResponseBody(response);
  if (!response.ok) {
    const message = response.status >= 500 ? serverErrorMessageFor(path) : detailMessage(body) ?? "Koneksi ke backend gagal";
    if (!suppressErrorLog) {
      console.error("API request failed", { url, status: response.status, body });
    }
    if (shouldStopForAuthFailure(path, response.status)) {
      handleAuthRequired(SESSION_NOT_READY_MESSAGE);
    }
    throw new ApiError(message, { status: response.status, url, body, retryAfterMs: retryAfterMs(response) });
  }
  return body;
}

async function postJson(path, payload) {
  ensureUnsafeRequestAllowed("POST", path);
  const url = `${API_BASE_URL}${path}`;
  let response;
  const headers = {
    "Content-Type": "application/json",
    ...(path === "/auth/login" ? {} : csrfHeaders("POST")),
  };
  try {
    response = await fetch(url, {
      method: "POST",
      credentials: "include",
      headers,
      body: JSON.stringify(payload),
    });
  } catch (error) {
    console.error("Network request failed", { url, error });
    throw new ApiError("API tidak dapat dihubungi", { url, cause: error });
  }

  const body = await readResponseBody(response);
  if (!response.ok) {
    const message =
      response.status >= 500
        ? serverErrorMessageFor(path)
        : detailMessage(body) ?? "Gambar gagal dikirim";
    console.error("API request failed", { url, status: response.status, body });
    if (shouldStopForAuthFailure(path, response.status)) {
      handleAuthRequired(SESSION_NOT_READY_MESSAGE);
    }
    throw new ApiError(message, { status: response.status, url, body, retryAfterMs: retryAfterMs(response) });
  }
  return body;
}

async function apiJson(method, path, payload) {
  const upperMethod = String(method).toUpperCase();
  const url = `${API_BASE_URL}${path}`;
  ensureUnsafeRequestAllowed(upperMethod, path);

  const headers = {
    ...csrfHeaders(upperMethod),
  };

  const options = {
    method: upperMethod,
    credentials: "include",
    headers,
  };

  if (payload !== undefined) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(payload);
  }

  let response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    console.error("Network request failed", { url, error });
    throw new ApiError("API tidak dapat dihubungi", { url, cause: error });
  }

  const body = await readResponseBody(response);
  if (!response.ok) {
    const message = detailMessage(body) ?? "Permintaan gagal";
    if (response.status === 403 && body?.detail && String(body.detail).includes("CSRF")) {
      console.warn("CSRF validation failed", { url, status: response.status, body });
      handleAuthRequired(SESSION_NOT_READY_MESSAGE);
      throw new ApiError("Sesi keamanan tidak valid. Silakan login ulang.", { status: response.status, url, body });
    }
    console.error("API request failed", { url, status: response.status, body });
    if (shouldStopForAuthFailure(path, response.status)) {
      handleAuthRequired(SESSION_NOT_READY_MESSAGE);
    }
    throw new ApiError(message, { status: response.status, url, body, retryAfterMs: retryAfterMs(response) });
  }
  return body;
}

function captureSingleFrame({ quality = 0.84, maxWidth = 720 } = {}) {
  const sourceWidth = elements.camera.videoWidth || 640;
  const sourceHeight = elements.camera.videoHeight || 480;
  const scale = Math.min(1, maxWidth / sourceWidth);
  const width = Math.max(1, Math.round(sourceWidth * scale));
  const height = Math.max(1, Math.round(sourceHeight * scale));
  const canvas = frameCanvas ?? document.createElement("canvas");
  frameCanvas = canvas;
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  // Capture the raw camera frame. The mirrored selfie preview is CSS-only so
  // backend yaw, bbox, and pgvector embedding data stay in camera coordinates.
  context.drawImage(elements.camera, 0, 0, width, height);
  return canvas.toDataURL("image/jpeg", quality).split(",")[1];
}

async function captureBurst({ quality = 0.84, maxWidth = 720, delayMs = 120 } = {}) {
  const frames = [];
  for (let index = 0; index < 3; index += 1) {
    frames.push({ frame_b64: captureSingleFrame({ quality, maxWidth }), pose_hint: null });
    if (index < 2) {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }
  return frames;
}

async function captureAttendanceFrames() {
  return captureBurst({ quality: 0.72, maxWidth: 640, delayMs: 60 });
}

async function startAttendanceMode() {
  closeIdentityModal();
  clearTransitionTimer();
  state.attendanceRequestInFlight = false;
  state.attendanceLastRequestAt = 0;
  state.attendanceDynamicDelay = ATTENDANCE_SCAN_INTERVAL_MS;
  state.attendancePausedUntil = 0;
  state.attendanceCooldownUntil = 0;
  state.attendanceLastResponse = null;
  state.attendanceThumbnail = null;
  state.attendanceConsecutiveErrors = 0;
  state.attendanceSessionNotice = "";
  state.pendingAttendance = null;
  state.attendanceConfirmInFlight = false;
  state.selectedAttendanceClassId = null;
  state.selectedAttendanceSessionId = null;
  state.availableAttendanceClasses = [];
  state.availableAttendanceSessions = [];
  state.attendanceClassLookupInFlight = false;
  state.attendanceClassLoadError = "";
  state.attendanceSessionLookupInFlight = false;
  state.attendanceSessionLoadError = "";
  state.attendanceSessionLookupDone = false;
  attendanceSessionLookupPromise = null;
  setScreen("recognize");
  await loadAttendanceClasses();
  state.attendanceStatus = "no_session";
  renderAttendance();
}

function startAttendanceLoop() {
  if (!state.selectedAttendanceSessionId) {
    return;
  }
  if (state.attendanceLoopId) {
    return;
  }
  state.attendanceLoopId = window.setInterval(autoAttendanceTick, ATTENDANCE_TICK_MS);
  window.setTimeout(autoAttendanceTick, 0);
}

function stopAttendanceLoop() {
  if (state.attendanceLoopId) {
    window.clearInterval(state.attendanceLoopId);
    state.attendanceLoopId = null;
  }
  state.attendancePausedUntil = 0;
  state.attendanceCooldownUntil = 0;
  state.attendanceRequestInFlight = false;
  state.attendanceConfirmInFlight = false;
  state.pendingAttendance = null;
  hideAttendanceConfirmModal();
}

function updateAttendanceStatusFromResponse(response, checkinRequested) {
  const recognitionStatus = responseRecognitionStatus(response);
  if (isQualityRejection(response)) {
    state.attendanceStatus = "quality_rejected";
    state.uiHint = qualityGuidanceMessage(response);
    state.attendancePausedUntil = Date.now() + 900;
    showAttendanceToast("warning", qualityGuidanceMessage(response), 1500);
    return;
  }
  if (response.reason === "candidate_margin_too_small") {
    state.attendanceStatus = "ambiguous";
    state.uiHint = "Data wajah terlalu mirip. Coba ulangi posisi wajah.";
    state.attendancePausedUntil = Date.now() + ATTENDANCE_RESULT_PAUSE_MS;
    showAttendanceToast("warning", "Data wajah terlalu mirip", 1800);
    return;
  }
  if (recognitionStatus === "no_matching_session") {
    state.attendanceStatus = recognitionStatus;
    state.uiHint = attendanceMessageFromResponse(response);
    state.attendancePausedUntil = Date.now() + 3000;
    showAttendanceEdgeSheet({
      title: "Tidak ada jadwal sesuai",
      message: "Wajah dikenali, tetapi tidak ada sesi absensi yang aktif untuk kelas ini saat ini.",
      actions: [
        { label: "Tutup", variant: "secondary", handler: () => { discardPendingAttendance(); } },
        { label: "Coba Lagi", variant: "primary", handler: () => { discardPendingAttendance(); } },
      ],
    });
    return;
  }
  if (recognitionStatus === "multiple_matching_sessions") {
    const sessions = response?.matching_sessions ?? response?.sessions ?? [];
    if (sessions.length === 0) {
      showAttendanceConfirmModal(response);
      return;
    }
    state.attendanceStatus = recognitionStatus;
    state.uiHint = attendanceMessageFromResponse(response);
    state.attendancePausedUntil = Date.now() + 5000;
    const sessionActions = sessions.slice(0, 3).map((s) => ({
      label: s.session_name ?? s.session_code ?? "Pilih",
      variant: "primary",
      handler: () => {
        state.pendingAttendance = { response, photo: attendancePreviewPhoto(response) };
        state.attendanceLastResponse = { ...response, resolved_session: s };
        state.attendanceStatus = "recognized";
        state.uiHint = "Periksa detail absensi";
        state.attendancePausedUntil = Number.POSITIVE_INFINITY;
        showAttendanceConfirmModal({ ...response, resolved_session: s });
      },
    }));
    showAttendanceEdgeSheet({
      title: "Pilih jadwal",
      message: "Ditemukan lebih dari satu sesi yang sesuai. Pilih salah satu untuk melanjutkan.",
      actions: [
        ...sessionActions,
        { label: "Batal", variant: "secondary", handler: () => { discardPendingAttendance(); } },
      ],
    });
    return;
  }
  if (recognitionStatus === "recognized") {
    const hasResolvedSession = Boolean(response?.resolved_session);
    if (hasResolvedSession) {
      const photo = attendancePreviewPhoto(response);
      state.pendingAttendance = { response, photo };
      state.attendanceLastResponse = response;
      state.attendanceStatus = "recognized";
      state.uiHint = "Periksa detail absensi";
      state.attendancePausedUntil = Number.POSITIVE_INFINITY;
      showAttendanceConfirmModal(response);
      return;
    }
    state.attendanceStatus = "recognized";
    state.uiHint = "Periksa detail absensi.";
    state.attendancePausedUntil = Number.POSITIVE_INFINITY;
    showAttendanceConfirmModal(response);
    return;
  }
  if (responseIsCooldown(response)) {
    state.attendanceStatus = "cooldown";
    state.uiHint = "Tunggu sebentar sebelum mencoba lagi";
    state.attendancePausedUntil = Date.now() + Math.min((response.cooldown_remaining_seconds ?? 2) * 1000, 2200);
    if (response.cooldown_remaining_seconds) {
      state.attendanceCooldownUntil = Date.now() + response.cooldown_remaining_seconds * 1000;
    }
    showAttendanceToast("warning", "Tunggu sebentar", 1800);
    return;
  }
  if (response.reason === "not_in_selected_class") {
    state.attendanceStatus = "not_in_selected_class";
    state.uiHint = "Wajah tidak terdaftar pada kelas ini";
    state.attendancePausedUntil = Date.now() + ATTENDANCE_RESULT_PAUSE_MS;
    showAttendanceToast("warning", "Wajah tidak terdaftar pada kelas ini", 2000);
    return;
  }
  if (recognitionStatus === "session_inactive") {
    handleInactiveAttendanceSession();
    showAttendanceToast("warning", "Tidak ada jadwal sesuai", 2000);
    return;
  }
  state.attendanceStatus = "unknown";
  state.uiHint = recognitionRejectionMessage(response);
  state.attendancePausedUntil = Date.now() + ATTENDANCE_RESULT_PAUSE_MS;
  showAttendanceToast("error", "Wajah tidak dikenali", 1500);
}

function handleInactiveAttendanceSession(message = "Sesi absensi sudah tidak aktif") {
  stopAttendanceLoop();
  forgetSessionCode({ notice: message });
  resetAttendanceSessionLookup();
  state.attendanceStatus = "session_inactive";
  state.uiHint = message;
  state.attendancePausedUntil = Date.now() + ATTENDANCE_RESULT_PAUSE_MS;
  refreshAttendanceSessionCode({ force: true, staleMessage: message });
}

function formatAttendanceDebug({ endpoint, sessionCode, frames = [], response = null, error = null }) {
  const summary = qualitySummaryFromResponse(response);
  const debug = {
    endpoint: endpoint ?? "-",
    selected_session_code: sessionCode ?? selectedAttendanceSessionCode(),
    device_code: DEVICE_CODE,
    frame_count: frames.length,
    frame_b64_sizes: frames.map((frame, index) => ({
      index: index + 1,
      chars: frame?.frame_b64?.length ?? 0,
    })),
    decision: response?.decision ?? null,
    recognition_status: responseRecognitionStatus(response),
    reason: response?.reason ?? null,
    dominant_reason: summary?.dominant_reason ?? null,
    reason_counts: summary?.reason_counts ?? summary?.reasons ?? {},
    quality_mode: summary?.quality_mode ?? null,
    quality_frames: qualityFramesFromResponse(response).map((frame) => ({
      index: frame.index,
      accepted: frame.accepted,
      reason: frame.reason,
      face_width_px: frame.face_width_px ?? null,
      min_face_width_px: frame.min_face_width_px ?? null,
      face_size_ratio: frame.face_size_ratio ?? null,
      face_box_normalized: frame.face_box_normalized ?? null,
      blur_score: frame.blur_score ?? null,
      min_blur_score: frame.min_blur_score ?? null,
      brightness_score: frame.brightness_score ?? null,
      liveness_score: frame.liveness_score ?? null,
      face_count: frame.face_count ?? null,
      face_center_offset_x: frame.face_center_offset_x ?? null,
      face_center_offset_y: frame.face_center_offset_y ?? null,
    })),
    error: error ? attendanceErrorSummary(error) : null,
  };
  return JSON.stringify(debug, null, 2);
}

async function sendAttendanceScan({ manual = false } = {}) {
  if (!state.selectedAttendanceSessionId) {
    return;
  }
  if (!state.cameraReady || state.attendanceRequestInFlight || state.pendingAttendance) {
    return;
  }
  let endpoint = null;
  let frames = [];
  try {
    state.attendanceRequestInFlight = true;
    state.attendanceStatus = "recognizing";
    state.uiHint = manual ? "Mengenali sekali..." : "Mengenali wajah...";
    renderAttendance();

    const requestStartedAt = Date.now();
    state.attendanceLastRequestAt = requestStartedAt;
    frames = await captureAttendanceFrames();
    state.attendanceThumbnail = frames[0]?.frame_b64 ? `data:image/jpeg;base64,${frames[0].frame_b64}` : null;
    endpoint = attendanceEndpoint();
    const response = await postJson(endpoint, attendancePayload(frames));
    if (state.mode !== "recognize") {
      return;
    }

    state.attendanceLastResponse = response;
    state.attendanceConsecutiveErrors = 0;
    updateAttendanceStatusFromResponse(response, false);
    elements.recognitionResult.textContent = formatAttendanceDebug({
      endpoint,
      sessionCode: response?.resolved_session?.session_code ?? null,
      frames,
      response,
    });

    const elapsedMs = Date.now() - requestStartedAt;
    state.attendanceDynamicDelay =
      elapsedMs > 1000 ? clamp(elapsedMs + 220, ATTENDANCE_SCAN_INTERVAL_MS, ATTENDANCE_MAX_BACKOFF_MS) : ATTENDANCE_SCAN_INTERVAL_MS;
    renderAttendance();
  } catch (error) {
    if (state.mode !== "recognize") {
      return;
    }
    state.attendanceConsecutiveErrors += 1;
    state.attendanceStatus = "error";
    state.uiHint = state.attendanceConsecutiveErrors >= 3
      ? "API backend offline / tidak dapat terhubung ke server"
      : attendanceErrorSummary(error);
    state.attendancePausedUntil = Date.now() + clamp(900 * state.attendanceConsecutiveErrors, 1200, ATTENDANCE_MAX_BACKOFF_MS);
    state.attendanceDynamicDelay = clamp(ATTENDANCE_SCAN_INTERVAL_MS * (state.attendanceConsecutiveErrors + 1), 1200, ATTENDANCE_MAX_BACKOFF_MS);
    state.attendanceLastResponse = null;
    elements.recognitionResult.textContent = formatAttendanceDebug({
      endpoint,
      sessionCode: null,
      frames,
      error,
    });
    renderAttendance();
  } finally {
    state.attendanceRequestInFlight = false;
    state.attendanceLastRequestAt = Date.now();
    if (state.mode === "recognize") {
      renderAttendance();
    }
  }
}

async function confirmPendingAttendance({ auto = false } = {}) {
  const pending = state.pendingAttendance;
  const response = pending?.response;
  const person = response?.person;
  const session = response?.resolved_session;
  if (!pending || !person?.person_id || !session?.session_code || state.attendanceConfirmInFlight) {
    return;
  }
  try {
    state.attendanceConfirmInFlight = true;
    state.attendanceStatus = "confirming";
    elements.attendanceConfirmAccept.disabled = true;
    elements.attendanceConfirmRetry.disabled = true;
    renderAttendance();
    const confirmResponse = await postJson("/attendance/confirm", {
      person_id: person.person_id,
      session_code: session.session_code,
      device_code: DEVICE_CODE,
      confidence: response.confidence ?? null,
      captured_face_b64_or_uri: response.captured_face_b64 ?? null,
      recognition_token: response.pending_attendance_token ?? null,
    });
    if (responseIsCooldown(confirmResponse)) {
      state.attendanceLastResponse = {
        ...response,
        decision: "rejected",
        recognition_status: "cooldown",
        reason: "cooldown",
        cooldown_remaining_seconds: confirmResponse.cooldown_remaining_seconds,
      };
      state.attendanceStatus = "cooldown";
      state.uiHint = "Tunggu sebentar sebelum absen lagi";
      state.attendanceCooldownUntil = Date.now() + (confirmResponse.cooldown_remaining_seconds ?? 2) * 1000;
      state.attendancePausedUntil = state.attendanceCooldownUntil;
      state.pendingAttendance = null;
      hideAttendanceConfirmModal();
      showAttendanceToast("warning", "Tunggu sebentar", 1800);
      return;
    }
    appendSuccessfulAttendance(confirmResponse);
    state.attendanceLastResponse = {
      ...response,
      decision: "accepted",
      recognition_status: "recognized",
      reason: auto ? "auto_confirmed" : "confirmed_by_user",
      cooldown_remaining_seconds: confirmResponse.cooldown_remaining_seconds,
    };
    state.attendanceStatus = "accepted";
    state.uiHint = "Absensi berhasil";
    state.attendanceCooldownUntil = Date.now() + (confirmResponse.cooldown_remaining_seconds ?? 0) * 1000;
    state.attendancePausedUntil = Date.now() + ATTENDANCE_SUCCESS_PAUSE_MS;
    state.pendingAttendance = null;
    hideAttendanceConfirmModal();
    playAcceptedFeedback();
    showAttendanceToast("success", `Berhasil — ${person.full_name}`, 2200);
  } catch (error) {
    if (authFailureError(error)) {
      return;
    }
    state.attendanceStatus = "error";
    state.uiHint = attendanceErrorSummary(error);
    state.attendancePausedUntil = Date.now() + ATTENDANCE_RESULT_PAUSE_MS;
    showAttendanceToast("error", "Gangguan koneksi", 2000);
  } finally {
    state.attendanceConfirmInFlight = false;
    if (state.pendingAttendance) {
      elements.attendanceConfirmAccept.disabled = false;
      elements.attendanceConfirmRetry.disabled = false;
    }
    if (state.mode === "recognize") {
      renderAttendance();
    }
  }
}

function autoAttendanceTick() {
  if (!state.selectedAttendanceSessionId) {
    return;
  }
  if (state.mode !== "recognize" || !state.cameraReady || state.attendanceRequestInFlight || state.pendingAttendance) {
    return;
  }
  const now = Date.now();
  if (now < state.attendancePausedUntil) {
    renderAttendance();
    return;
  }
  if (now - state.attendanceLastRequestAt < state.attendanceDynamicDelay) {
    return;
  }
  state.attendanceStatus = "scanning";
  state.attendanceLastResponse = null;
  sendAttendanceScan();
}

function startAutoCaptureLoop() {
  if (!authSessionReady()) {
    handleAuthRequired(SESSION_NOT_READY_MESSAGE, { intendedMode: "enroll" });
    return;
  }
  if (state.captureLoopId) {
    return;
  }
  state.captureLoopId = window.setInterval(autoCaptureTick, AUTO_CAPTURE_TICK_MS);
}

function stopAutoCaptureLoop() {
  if (!state.captureLoopId) {
    return;
  }
  window.clearInterval(state.captureLoopId);
  state.captureLoopId = null;
  state.stableSince = null;
  state.enrollmentFrameInFlight = false;
  updateCountdown(null);
}

function clearTransitionTimer() {
  if (!state.transitionTimerId) {
    return;
  }
  window.clearTimeout(state.transitionTimerId);
  state.transitionTimerId = null;
}

function resetEnrollmentSession() {
  stopAutoCaptureLoop();
  stopAttendanceLoop();
  clearTransitionTimer();
  closeIdentityModal();
  state.mode = "enroll";
  elements.enrollModeButton.classList.add("is-active");
  elements.recognizeModeButton.classList.remove("is-active");
  elements.enrollmentPanel.classList.remove("recognition-active");
  state.enrollmentSessionId = null;
  state.personId = null;
  state.requiredPoses = [...POSE_SEQUENCE];
  state.acceptedPerPose = 0;
  state.remainingPerPose = Object.fromEntries(POSE_SEQUENCE.map((pose) => [pose, 0]));
  state.nextPose = "front";
  state.displayPose = null;
  state.progressPercent = 0;
  state.captureStatus = "idle";
  state.uiHint = "Ikuti panduan di layar.";
  state.lastFrameResponse = null;
  state.requestInFlight = false;
  state.enrollmentFrameInFlight = false;
  state.lastRequestAt = 0;
  state.lastEnrollmentFrameAt = 0;
  state.enrollmentBackoffUntil = 0;
  state.dynamicCaptureDelay = AUTO_CAPTURE_INTERVAL_MS;
  state.autoFinishStarted = false;
  state.consecutiveCaptureErrors = 0;
  state.lastError = null;
  setEnrollmentState("idle");
  updateMetrics(null);
  elements.result.textContent = "siap";
  setScreen("home");
  renderWizard();
}

async function startEnrollment(event) {
  event.preventDefault();
  if (!authSessionReady()) {
    handleAuthRequired(SESSION_NOT_READY_MESSAGE, { intendedMode: "enroll" });
    return;
  }
  try {
    stopAutoCaptureLoop();
    closeIdentityModal();
    setScreen("capture");
    setEnrollmentState("starting");
    state.captureStatus = "starting";
    state.uiHint = "Menyiapkan kamera...";
    renderWizard();
    // Guarantee a live camera before capturing — fixes re-enrollment on
    // Android where the previous stream had been dropped.
    try {
      await ensureCameraReady();
    } catch (cameraError) {
      setEnrollmentState("error");
      state.captureStatus = "error";
      state.cameraWarning = cameraWarningFor(cameraError);
      state.uiHint = state.cameraWarning;
      elements.startButton.disabled = false;
      renderWizard();
      return;
    }
    state.uiHint = "Memulai pendaftaran wajah...";
    state.lastFrameResponse = null;
    state.autoFinishStarted = false;
    state.consecutiveCaptureErrors = 0;
    state.dynamicCaptureDelay = AUTO_CAPTURE_INTERVAL_MS;
    state.lastEnrollmentFrameAt = 0;
    state.enrollmentBackoffUntil = 0;
    state.enrollmentFrameInFlight = false;
    state.lastError = null;
    state.displayPose = null;
    clearTransitionTimer();
    elements.startButton.disabled = true;
    renderWizard();

    const payload = readIdentityForm();
    const response = await postJson("/enroll/start", payload);
    state.enrollmentSessionId = response.enrollment_session_id;
    state.personId = response.person_id;
    state.requiredPoses = response.required_poses;
    state.acceptedPerPose = response.accepted_per_pose;
    state.remainingPerPose = response.remaining_per_pose;
    state.nextPose = response.required_poses[0] ?? null;
    state.progressPercent = 0;
    state.captureStatus = "searching_face";
    state.uiHint = "Perekaman otomatis aktif. Posisikan wajah di dalam lingkaran.";
    setEnrollmentState("searching_face");
    elements.result.textContent = JSON.stringify(response, null, 2);
    updateMetrics(null);
    if (elements.enrollStudentName) {
      elements.enrollStudentName.textContent = payload.full_name || "";
    }
    renderWizard();
    startAutoCaptureLoop();
  } catch (error) {
    if (authFailureError(error)) {
      return;
    }
    setEnrollmentState("error");
    state.captureStatus = "error";
    state.uiHint = errorSummary(error);
    state.lastError = error;
    renderWizard();
    elements.result.textContent = JSON.stringify({ error: errorSummary(error) }, null, 2);
  } finally {
    renderWizard();
  }
}

async function captureEnrollmentFrame({ manual = false } = {}) {
  if (!authSessionReady()) {
    handleAuthRequired(SESSION_NOT_READY_MESSAGE, { intendedMode: "enroll" });
    return;
  }
  const now = Date.now();
  if (
    !state.enrollmentSessionId ||
    state.requestInFlight ||
    state.enrollmentFrameInFlight ||
    allPosesComplete() ||
    now < state.enrollmentBackoffUntil ||
    now - state.lastEnrollmentFrameAt < ENROLLMENT_FRAME_MIN_INTERVAL_MS
  ) {
    return;
  }
  const pose = currentPose();
  if (!pose) {
    return;
  }
  try {
    state.requestInFlight = true;
    state.enrollmentFrameInFlight = true;
    const requestStartedAt = Date.now();
    state.lastRequestAt = requestStartedAt;
    state.lastEnrollmentFrameAt = requestStartedAt;
    setEnrollmentState("capturing");
    state.captureStatus = "capturing";
    state.uiHint = manual ? "Gambar manual sedang dianalisis..." : "Merekam...";
    elements.faceOval.style.setProperty("--hold-progress", "1");
    elements.faceOval.style.setProperty("--hold-angle", "360deg");
    renderWizard();
    const response = await postJson("/enroll/frame", {
      enrollment_session_id: state.enrollmentSessionId,
      device_code: DEVICE_CODE,
      pose,
      frame_b64: captureSingleFrame(),
    });

    state.remainingPerPose = response.remaining_per_pose;
    state.nextPose = response.next_pose;
    state.progressPercent = response.progress_percent;
    state.captureStatus = response.accepted ? "accepted" : (response.capture_status || stateFromFrameResponse(response));
    state.uiHint = localizedHint(response);
    state.lastFrameResponse = response;
    state.consecutiveCaptureErrors = 0;
    state.lastError = null;
    state.stableSince = !response.accepted && responseLooksNearlyReady(response) && response.capture_status !== "stuck_adjust" ? Date.now() : null;
    const elapsedMs = Date.now() - requestStartedAt;
    state.dynamicCaptureDelay =
      elapsedMs > 850 ? clamp(elapsedMs + 180, AUTO_CAPTURE_INTERVAL_MS, MAX_CAPTURE_BACKOFF_MS) : AUTO_CAPTURE_INTERVAL_MS;
    if (response.retry_after_ms) {
      state.dynamicCaptureDelay = clamp(response.retry_after_ms, AUTO_CAPTURE_INTERVAL_MS, MAX_CAPTURE_BACKOFF_MS);
    }
    const flags = response.quality?.flags ?? {};
    if (!response.accepted) {
      if (
        flags.exactly_one_face === false ||
        flags.min_face_width === false ||
        distanceState(response).key === "too_close" ||
        response.capture_status === "stuck_adjust"
      ) {
        state.dynamicCaptureDelay = Math.max(state.dynamicCaptureDelay, 760);
      }
    }
    updateMetrics(response.quality);
    elements.result.textContent = JSON.stringify(response, null, 2);

    if (response.accepted) {
      setEnrollmentState("pose_complete");
      playAcceptedFeedback();
      state.dynamicCaptureDelay = AFTER_ACCEPT_DELAY_MS;
      scheduleAfterAcceptedFrame(pose, response);
    } else if (
      response.reason === "liveness_below_threshold" &&
      flags.exactly_one_face &&
      flags.min_face_width &&
      flags.face_centered_x &&
      flags.face_centered_y &&
      !state.livenessChallengeActive
    ) {
      setEnrollmentState("adjusting_position");
      state.captureStatus = "liveness_check";
      state.uiHint = "Verifikasi keaslian wajah...";
      renderWizard();
      showLivenessChallenge();
      state.dynamicCaptureDelay = 2000;
    } else {
      const nextState = stateFromFrameResponse(response);
      setEnrollmentState(nextState);
      state.captureStatus = nextState;
    }

    if (allPosesComplete()) {
      setEnrollmentState("pose_complete");
      state.captureStatus = "pose_complete";
      stopAutoCaptureLoop();
      renderWizard();
      if (!state.autoFinishStarted) {
        state.autoFinishStarted = true;
        window.setTimeout(() => finishEnrollment({ auto: true }), AFTER_ACCEPT_DELAY_MS);
      }
      return;
    }

    renderWizard();
  } catch (error) {
    if (authFailureError(error)) {
      return;
    }
    if (error instanceof ApiError && error.status === 429) {
      const backoffMs = Math.max(error.retryAfterMs ?? ENROLLMENT_RATE_LIMIT_BACKOFF_MS, ENROLLMENT_FRAME_MIN_INTERVAL_MS);
      state.enrollmentBackoffUntil = Date.now() + backoffMs;
      state.dynamicCaptureDelay = Math.max(state.dynamicCaptureDelay, backoffMs);
      state.captureStatus = "searching_face";
      state.uiHint = "Tunggu sebentar sebelum menangkap ulang";
      state.lastError = error;
      setEnrollmentState("searching_face");
      renderWizard();
      elements.result.textContent = JSON.stringify({ error: state.uiHint, retry_after_ms: backoffMs }, null, 2);
      return;
    }
    state.consecutiveCaptureErrors += 1;
    state.dynamicCaptureDelay = clamp(AUTO_CAPTURE_INTERVAL_MS * (state.consecutiveCaptureErrors + 1), 900, MAX_CAPTURE_BACKOFF_MS);
    state.captureStatus = "error";
    state.uiHint = errorSummary(error);
    state.lastError = error;
    if (state.consecutiveCaptureErrors >= 3) {
      setEnrollmentState("error");
      stopAutoCaptureLoop();
    } else {
      setEnrollmentState("searching_face");
    }
    renderWizard();
    elements.result.textContent = JSON.stringify({ error: errorSummary(error) }, null, 2);
  } finally {
    state.requestInFlight = false;
    state.enrollmentFrameInFlight = false;
    state.lastRequestAt = Date.now();
    renderWizard();
  }
}

function autoCaptureTick() {
  if (!authSessionReady()) {
    handleAuthRequired(SESSION_NOT_READY_MESSAGE, { intendedMode: "enroll" });
    return;
  }
  if (
    state.mode !== "enroll" ||
    !state.enrollmentSessionId ||
    state.requestInFlight ||
    state.enrollmentFrameInFlight ||
    allPosesComplete() ||
    state.enrollmentState === "pose_complete" ||
    state.enrollmentState === "next_pose" ||
    state.enrollmentState === "finishing" ||
    state.enrollmentState === "error"
  ) {
    return;
  }
  const now = Date.now();
  if (now < state.enrollmentBackoffUntil || now - state.lastEnrollmentFrameAt < ENROLLMENT_FRAME_MIN_INTERVAL_MS) {
    return;
  }
  if (state.stableSince) {
    setEnrollmentState("holding");
    const elapsed = now - state.stableSince;
    if (elapsed < STABILITY_WINDOW_MS) {
      updateCountdown(STABILITY_WINDOW_MS - elapsed);
      renderWizard();
      return;
    }
    elements.faceOval.style.setProperty("--hold-progress", "1");
    elements.faceOval.style.setProperty("--hold-angle", "360deg");
    captureEnrollmentFrame();
    return;
  }
  if (now - state.lastRequestAt < state.dynamicCaptureDelay) {
    return;
  }
  captureEnrollmentFrame();
}

async function finishEnrollment({ auto = false } = {}) {
  if (!authSessionReady()) {
    handleAuthRequired(SESSION_NOT_READY_MESSAGE, { intendedMode: "enroll" });
    return;
  }
  if (!state.enrollmentSessionId || state.enrollmentState === "finishing") {
    return;
  }
  try {
    stopAutoCaptureLoop();
    setEnrollmentState("finishing");
    state.captureStatus = "finishing";
    state.uiHint = auto ? "Semua pose selesai. Menyimpan pendaftaran..." : "Menyimpan pendaftaran...";
    renderWizard();
    const response = await postJson("/enroll/finish", { enrollment_session_id: state.enrollmentSessionId });
    setEnrollmentState("complete");
    state.captureStatus = "complete";
    state.uiHint = "Pendaftaran wajah berhasil.";
    state.progressPercent = 100;
    state.enrollmentSessionId = null;
    elements.result.textContent = JSON.stringify(response, null, 2);
    setScreen("complete");
    renderWizard();
  } catch (error) {
    if (authFailureError(error)) {
      return;
    }
    setEnrollmentState("error");
    state.captureStatus = "error";
    state.uiHint = errorSummary(error);
    state.lastError = error;
    renderWizard();
    elements.result.textContent = JSON.stringify({ error: errorSummary(error) }, null, 2);
  }
}

function cancelEnrollment() {
  resetEnrollmentSession();
}

async function runRecognitionBurst() {
  setMode("recognize");
  await sendAttendanceScan({ manual: true });
}

async function startCamera() {
  state.cameraStatus = "checking";
  state.cameraWarning = "";
  stopCameraStream();
  if (!navigator.mediaDevices?.getUserMedia) {
    const error = new Error("navigator.mediaDevices.getUserMedia is unavailable");
    error.name = "NotSupportedError";
    throw error;
  }
  await enumerateCameras();
  const requestedDeviceId = state.cameraSelectionMode === "manual" ? state.selectedCameraId : "";
  const attempts = cameraStartupAttempts(requestedDeviceId);
  const failures = [];
  let startupWarning = "";
  let stream = null;
  for (const attempt of attempts) {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: attempt.video, audio: false });
      const [track] = stream.getVideoTracks();
      if (!attempt.manual && cameraTrackLooksBack(track)) {
        const error = new Error("Selected camera is rear/environment-facing");
        error.name = "WrongFacingModeError";
        failures.push({ label: track?.label ? `${attempt.label}: ${track.label}` : attempt.label, error });
        stopMediaStream(stream);
        stream = null;
        continue;
      }
      if (attempt.fallbackForStoredCamera) {
        startupWarning = "Kamera tersimpan tidak dapat dimulai. Menggunakan kamera lain.";
      }
      break;
    } catch (error) {
      failures.push({ label: attempt.label, error });
      if (attempt.storedCamera) {
        storeCameraId("");
      }
      if (!shouldTryNextCamera(error)) {
        break;
      }
    }
  }
  if (!stream) {
    const lastError = failures.at(-1)?.error ?? new Error("Camera unavailable");
    throw cameraStartupError(lastError, failures);
  }
  state.cameraWarning = startupWarning;
  attachCameraStream(stream);
  await enumerateCameras();
}

function cameraStartupAttempts(requestedDeviceId) {
  const attempts = [];
  const seenDeviceIds = new Set();
  const addDeviceAttempt = (deviceId, label, storedCamera = false, manual = false) => {
    if (!deviceId || seenDeviceIds.has(deviceId)) return;
    seenDeviceIds.add(deviceId);
    attempts.push({
      label,
      video: { deviceId: { exact: deviceId } },
      storedCamera,
      manual,
      fallbackForStoredCamera: Boolean(requestedDeviceId && !storedCamera),
    });
  };
  const addConstraintAttempt = (label, video) => {
    attempts.push({
      label,
      video,
      storedCamera: false,
      manual: false,
      fallbackForStoredCamera: Boolean(requestedDeviceId),
    });
  };

  addDeviceAttempt(requestedDeviceId, "Kamera pilihan Admin", true, true);
  addConstraintAttempt("Kamera depan", { facingMode: { exact: "user" } });

  const labeledDevices = state.cameraDevices.map((device, index) => ({
    device,
    label: cameraLabel(device, index),
  }));
  labeledDevices
    .filter(({ label }) => cameraNameLooksFront(label) && !cameraNameLooksBack(label))
    .forEach(({ device, label }) => addDeviceAttempt(device.deviceId, label));

  addConstraintAttempt("Kamera depan/default", { facingMode: { ideal: "user" } });

  labeledDevices
    .filter(({ label }) => !cameraNameLooksFront(label) && !cameraNameLooksBack(label))
    .forEach(({ device, label }) => addDeviceAttempt(device.deviceId, label));

  addConstraintAttempt("Kamera default", true);
  return attempts;
}

function attachCameraStream(stream) {
  elements.camera.srcObject = stream;
  const [track] = stream.getVideoTracks();
  const settings = track?.getSettings?.() ?? {};
  if (settings.deviceId) rememberActiveCameraId(settings.deviceId);
  elements.camera.classList.toggle("is-mirrored", VIDEO_PREVIEW_MIRRORED);
  elements.cameraStage.dataset.previewMirrored = VIDEO_PREVIEW_MIRRORED ? "true" : "false";
  state.cameraReady = true;
  state.cameraStatus = "connected";
  // Auto-recover when the camera track drops (USB unplugged, device slept).
  // A kiosk has no operator to reload the page, so we restart the stream once.
  if (track) {
    track.addEventListener(
      "ended",
      () => {
        if (state.cameraRecovering) return;
        state.cameraRecovering = true;
        state.cameraStatus = "disconnected";
        state.cameraWarning = "Kamera terputus, menyambungkan ulang...";
        renderWizard();
        restartCamera()
          .catch(() => {
            state.cameraWarning = "Kamera tidak dapat disambungkan ulang. Periksa koneksi kamera.";
          })
          .finally(() => {
            state.cameraRecovering = false;
          });
      },
      { once: true },
    );
  }
  elements.status.textContent = JSON.stringify(
    { camera: "ready", label: track?.label ?? "default", tracks: stream.getVideoTracks().length, device_code: DEVICE_CODE, api_base_url: API_BASE_URL },
    null,
    2,
  );
  renderWizard();
  if (state.mode === "recognize") startAttendanceLoop();
}

async function enumerateCameras() {
  if (!navigator.mediaDevices?.enumerateDevices) {
    state.cameraDevices = [];
    state.cameraStatus = state.cameraReady ? "connected" : "disconnected";
    state.cameraWarning = "Browser tidak mendukung daftar kamera.";
    return;
  }
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    state.cameraDevices = devices.filter((device) => device.kind === "videoinput");
    if (state.cameraDevices.length > 0 && !state.cameraDevices.some((device) => device.deviceId === state.selectedCameraId)) {
      if (state.selectedCameraId) state.cameraWarning = "Kamera tersimpan tidak ditemukan.";
      if (!state.cameraReady) storeCameraId("");
    }
    state.cameraStatus = state.cameraReady || state.cameraDevices.length > 0 ? "connected" : "disconnected";
  } catch (error) {
    state.cameraStatus = "disconnected";
    state.cameraWarning = "Kamera tidak dapat diperiksa.";
  }
}

function stopCameraStream() {
  const stream = elements.camera.srcObject;
  stopMediaStream(stream);
  elements.camera.srcObject = null;
  state.cameraReady = false;
}

async function restartCamera() {
  stopCameraStream();
  await startCamera();
}

elements.startForm.addEventListener("submit", startEnrollment);
elements.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.loginError.classList.add("is-hidden");
  try {
    const payload = formObject(elements.loginForm);
    const response = await postJson("/auth/login", payload);
    if (!csrfToken()) {
      state.adminUser = null;
      updateAuthUi();
      showLogin(SESSION_NOT_READY_MESSAGE);
      return;
    }
    state.adminUser = response.user;
    updateAuthUi();
    const nextMode = state.pendingModeAfterLogin || "admin";
    state.pendingModeAfterLogin = null;
    if (nextMode === "recognize") {
      setMode("recognize");
    } else if (nextMode === "enroll") {
      setMode("enroll");
      loadAdminData().finally(() => populateIdentityClassOptions());
      showIdentityModal();
    } else {
      await openAdmin();
    }
  } catch (error) {
    elements.loginError.textContent = errorSummaryFor(error, "Login gagal");
    elements.loginError.classList.remove("is-hidden");
  }
});
elements.loginCancelButton.addEventListener("click", () => {
  state.pendingModeAfterLogin = "recognize";
  stopAutoCaptureLoop();
  stopAttendanceLoop();
  state.mode = "home";
  setScreen("home");
});
elements.adminLogoutButton.addEventListener("click", async () => {
  await apiJson("POST", "/auth/logout").catch(() => null);
  state.adminUser = null;
  state.pendingModeAfterLogin = "recognize";
  updateAuthUi();
  handleAuthRequired(SESSION_NOT_READY_MESSAGE, { intendedMode: "recognize" });
});
elements.adminScreen.addEventListener("submit", handleAdminForm);
elements.adminScreen.addEventListener("click", handleAdminAction);
elements.adminPrimaryAction.addEventListener("click", () => {
  const firstInput = elements.adminBody.querySelector(".admin-form input, .admin-form select");
  firstInput?.focus();
});
document.querySelectorAll(".admin-nav").forEach((button) => {
  button.addEventListener("click", async () => {
    state.adminView = button.dataset.adminView;
    state.adminEdit = null;
    await loadAdminData();
    renderAdmin();
  });
});
elements.adminBody.addEventListener("click", (event) => {
  if (event.target?.id === "admin-start-enrollment") {
    setMode("enroll");
    showIdentityModal();
  }
});

// Click any face photo to open it full-size in the lightbox.
const photoLightbox = document.getElementById("photo-lightbox");
const photoLightboxImg = document.getElementById("photo-lightbox-img");
function openPhotoLightbox(src) {
  if (!photoLightbox || !photoLightboxImg || !src) return;
  photoLightboxImg.src = src;
  photoLightbox.classList.add("is-open");
}
function closePhotoLightbox() {
  if (!photoLightbox || !photoLightboxImg) return;
  photoLightbox.classList.remove("is-open");
  photoLightboxImg.src = "";
}
elements.adminBody.addEventListener("click", (event) => {
  const img = event.target?.closest?.(".face-thumb");
  if (img && img.getAttribute("src")) {
    event.preventDefault();
    openPhotoLightbox(img.getAttribute("src"));
  }
});
photoLightbox?.addEventListener("click", (event) => {
  if (event.target === photoLightbox || event.target?.id === "photo-lightbox-close") {
    closePhotoLightbox();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closePhotoLightbox();
});
elements.homeEnrollButton.addEventListener("click", () => {
  setMode("enroll");
  if (state.adminUser) {
    loadAdminData().finally(() => populateIdentityClassOptions());
    showIdentityModal();
  }
});
elements.homeRecognizeButton.addEventListener("click", () => setMode("recognize"));
elements.identityCancelButton.addEventListener("click", closeIdentityModal);
document.getElementById("student-id")?.addEventListener("input", (event) => {
  event.currentTarget.dataset.userEdited = "true";
});
elements.attendanceSessionSelect.addEventListener("change", async (event) => {
  const value = event.target.value ? String(event.target.value).trim() : null;
  state.attendanceSessionNotice = "";
  if (!state.selectedAttendanceClassId) {
    if (value) {
      state.selectedAttendanceClassId = value;
      state.availableAttendanceSessions = [];
      state.attendanceSessionLookupDone = false;
      await loadSessionsForClass(value);
      renderAttendance();
    }
    return;
  }
  const sessionId = value;
  if (sessionId) {
    const session = state.availableAttendanceSessions.find((s) => s.session_id === sessionId);
    if (session) {
      rememberSession(session);
    }
  } else {
    forgetSessionCode();
  }
  if (state.selectedAttendanceSessionId) {
    state.attendanceStatus = "scanning";
    state.attendanceLastResponse = null;
    startAttendanceLoop();
  } else {
    state.attendanceStatus = "no_session";
    state.attendanceLastResponse = null;
    stopAttendanceLoop();
  }
  renderAttendance();
});
elements.attendanceConfirmAccept.addEventListener("click", confirmPendingAttendance);
elements.attendanceConfirmRetry.addEventListener("click", discardPendingAttendance);
elements.attendanceConfirmCancel.addEventListener("click", () => {
  discardPendingAttendance();
  stopAttendanceLoop();
  state.selectedAttendanceClassId = null;
  state.selectedAttendanceSessionId = null;
  state.availableAttendanceClasses = [];
  state.availableAttendanceSessions = [];
  state.attendanceStatus = "no_session";
  renderAttendance();
});
elements.captureButton.addEventListener("click", () => captureEnrollmentFrame({ manual: true }));
elements.finishButton.addEventListener("click", () => finishEnrollment());
elements.cancelButton.addEventListener("click", cancelEnrollment);
elements.nextPersonButton.addEventListener("click", resetEnrollmentSession);
elements.recognitionButton.addEventListener("click", runRecognitionBurst);
elements.enrollModeButton.addEventListener("click", () => {
  if (state.enrollmentSessionId && !isTerminalEnrollmentState()) {
    setMode("enroll");
  } else {
    resetEnrollmentSession();
  }
});
elements.recognizeModeButton.addEventListener("click", () => setMode("recognize"));
elements.adminModeButton.addEventListener("click", () => setMode("admin"));
if (elements.attendanceChangeSessionBtn) {
  elements.attendanceChangeSessionBtn.addEventListener("click", () => {
    stopAttendanceLoop();
    forgetSessionCode();
    state.attendanceStatus = "no_session";
    state.attendanceLastResponse = null;
    state.pendingAttendance = null;
    hideAttendanceConfirmModal();
    renderAttendance();
  });
}
if (elements.attendanceCloseBtn) {
  elements.attendanceCloseBtn.addEventListener("click", () => {
    stopAttendanceLoop();
    state.attendanceStatus = "no_session";
    state.attendanceLastResponse = null;
    state.attendanceLastRequestAt = 0;
    state.attendanceConsecutiveErrors = 0;
    state.selectedAttendanceClassId = null;
    state.selectedAttendanceSessionId = null;
    state.availableAttendanceClasses = [];
    state.availableAttendanceSessions = [];
    setScreen("home");
    state.mode = "idle";
    elements.enrollModeButton.classList.remove("is-active");
    elements.recognizeModeButton.classList.remove("is-active");
    elements.adminModeButton.classList.remove("is-active");
  });
}

renderWizard();
(async function bootstrapKiosk() {
  // Public kiosk: attendance mode does NOT require admin login.
  // Silently refresh admin session so the Admin / Daftarkan Wajah buttons
  // light up if a cookie is already valid, but never force the login screen.
  await refreshMe({ showLoginOnFailure: false, intendedMode: "recognize" }).catch(() => false);
  // A logged-in admin who reloads should land on the home screen to choose an
  // action, NOT be dropped straight into attendance scanning. Only an
  // anonymous public kiosk auto-starts attendance mode.
  if (state.adminUser) {
    showHomeScreen();
  } else {
    setMode("recognize");
  }
  startCamera().catch((error) => {
    setEnrollmentState("error");
    state.cameraReady = false;
    state.cameraStatus = "disconnected";
    state.attendanceStatus = "error";
    state.cameraWarning = cameraWarningFor(error);
    state.uiHint = state.cameraWarning;
    const details = cameraErrorDetails(error);
    elements.status.textContent = JSON.stringify(details, null, 2);
    elements.recognitionResult.textContent = JSON.stringify(details, null, 2);
    setOverlay("Kamera tidak tersedia", "rejected");
    renderWizard();
  });
})();

