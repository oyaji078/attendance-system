import { kioskConfig } from "./config.js";

const API_BASE_URL = kioskConfig.apiBaseUrl;
const DEVICE_CODE = kioskConfig.deviceCode;
const POSE_SEQUENCE = ["front", "left_20", "right_20", "up_or_down"];
const POSE_COPY = {
  front: {
    title: "Front pose",
    instruction: "Look straight at the camera. Keep both eyes level, centered, and hold still.",
    cueClass: "pose-front",
  },
  left_20: {
    title: "Turn left",
    instruction: "Turn slightly to your left until your face is clearly angled, but keep your eyes visible.",
    cueClass: "pose-left",
  },
  right_20: {
    title: "Turn right",
    instruction: "Turn slightly to your right. Do not over-rotate or move out of frame.",
    cueClass: "pose-right",
  },
  up_or_down: {
    title: "Raise or lower your chin",
    instruction: "Tilt your chin slightly up or down. The kiosk will accept the angle that matches the final pose requirement.",
    cueClass: "pose-updown",
  },
};
const STATUS_COPY = {
  idle: "Idle",
  validating: "Validating",
  accepted: "Accepted",
  rejected: "Rejected",
  pose_complete: "Pose done",
  completed: "Completed",
};

const elements = {
  camera: document.getElementById("camera"),
  status: document.getElementById("status"),
  result: document.getElementById("result"),
  recognitionResult: document.getElementById("recognition-result"),
  overlay: document.getElementById("capture-overlay"),
  progressLabel: document.getElementById("progress-label"),
  progressFill: document.getElementById("progress-fill"),
  currentPoseTitle: document.getElementById("current-pose-title"),
  currentPoseInstruction: document.getElementById("current-pose-instruction"),
  uiHint: document.getElementById("ui-hint"),
  poseVisual: document.getElementById("pose-visual"),
  poseGrid: document.getElementById("pose-grid"),
  captureButton: document.getElementById("capture-pose"),
  finishButton: document.getElementById("finish-enrollment"),
  startForm: document.getElementById("enrollment-form"),
  startButton: document.getElementById("start-enrollment"),
  captureStatusBadge: document.getElementById("capture-status-badge"),
  recognitionButton: document.getElementById("capture-recognition"),
  enrollModeButton: document.getElementById("mode-enroll"),
  recognizeModeButton: document.getElementById("mode-recognize"),
  enrollmentPanel: document.getElementById("enrollment-panel"),
  recognitionPanel: document.getElementById("recognition-panel"),
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
};

const state = {
  mode: "enroll",
  enrollmentSessionId: null,
  personId: null,
  requiredPoses: [...POSE_SEQUENCE],
  acceptedPerPose: 0,
  remainingPerPose: Object.fromEntries(POSE_SEQUENCE.map((pose) => [pose, 0])),
  nextPose: "front",
  progressPercent: 0,
  captureStatus: "idle",
  uiHint: "Follow the step instructions and keep your face centered.",
};

function setMode(mode) {
  state.mode = mode;
  const enrollActive = mode === "enroll";
  elements.enrollModeButton.classList.toggle("is-active", enrollActive);
  elements.recognizeModeButton.classList.toggle("is-active", !enrollActive);
  elements.enrollmentPanel.classList.toggle("is-hidden", !enrollActive);
  elements.recognitionPanel.classList.toggle("is-hidden", enrollActive);
}

function poseTitle(pose) {
  return POSE_COPY[pose]?.title ?? pose;
}

function currentPose() {
  return state.nextPose ?? POSE_SEQUENCE.find((pose) => (state.remainingPerPose[pose] ?? 0) > 0) ?? "front";
}

function renderPoseGrid() {
  elements.poseGrid.innerHTML = "";
  for (const pose of state.requiredPoses) {
    const remaining = state.remainingPerPose[pose] ?? state.acceptedPerPose;
    const completed = state.acceptedPerPose > 0 && remaining === 0;
    const active = pose === currentPose() && !completed;
    const accepted = Math.max(state.acceptedPerPose - remaining, 0);
    const card = document.createElement("article");
    card.className = `pose-card${active ? " active" : ""}${completed ? " complete" : ""}`;
    card.innerHTML = `
      <p class="pose-label">${poseTitle(pose)}</p>
      <strong>${accepted}/${state.acceptedPerPose || 0}</strong>
      <span>${remaining} remaining</span>
    `;
    elements.poseGrid.appendChild(card);
  }
}

function setOverlay(text, tone = "idle") {
  elements.overlay.textContent = text;
  elements.overlay.className = `capture-overlay ${tone}`;
}

function setStatusBadge(status) {
  elements.captureStatusBadge.textContent = STATUS_COPY[status] ?? status;
  elements.captureStatusBadge.className = `status-pill ${status}`;
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

function renderWizard() {
  const pose = currentPose();
  const copy = POSE_COPY[pose] ?? POSE_COPY.front;
  elements.currentPoseTitle.textContent = copy.title;
  elements.currentPoseInstruction.textContent = copy.instruction;
  elements.poseVisual.className = `pose-visual ${copy.cueClass}`;
  elements.progressLabel.textContent = `${state.progressPercent.toFixed(0)}%`;
  elements.progressFill.style.width = `${state.progressPercent}%`;
  elements.uiHint.textContent = state.uiHint;
  elements.uiHint.className = `ui-hint ${state.captureStatus === "accepted" ? "accepted" : state.captureStatus === "rejected" ? "rejected" : "neutral"}`;
  elements.captureButton.disabled = !state.enrollmentSessionId || state.captureStatus === "validating" || !pose;
  const allDone = state.requiredPoses.every((requiredPose) => (state.remainingPerPose[requiredPose] ?? 0) === 0);
  elements.finishButton.disabled = !state.enrollmentSessionId || !allDone || state.captureStatus === "validating";
  setStatusBadge(state.captureStatus);
  renderPoseGrid();
}

function readIdentityForm() {
  const formData = new FormData(elements.startForm);
  return {
    student_id: String(formData.get("student_id") ?? "").trim(),
    full_name: String(formData.get("full_name") ?? "").trim(),
    email: String(formData.get("email") ?? "").trim() || null,
    device_code: DEVICE_CODE,
  };
}

async function postJson(path, payload) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok) {
    const detail = body?.detail ?? body;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body;
}

function captureSingleFrame() {
  const canvas = document.createElement("canvas");
  canvas.width = elements.camera.videoWidth || 640;
  canvas.height = elements.camera.videoHeight || 480;
  const context = canvas.getContext("2d");
  context.drawImage(elements.camera, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.92).split(",")[1];
}

async function captureBurst() {
  const frames = [];
  for (let index = 0; index < 3; index += 1) {
    frames.push({ frame_b64: captureSingleFrame(), pose_hint: null });
    await new Promise((resolve) => setTimeout(resolve, 120));
  }
  return frames;
}

async function startEnrollment(event) {
  event.preventDefault();
  try {
    elements.startButton.disabled = true;
    setOverlay("Starting enrollment...", "validating");
    const payload = readIdentityForm();
    const response = await postJson("/enroll/start", payload);
    state.enrollmentSessionId = response.enrollment_session_id;
    state.personId = response.person_id;
    state.requiredPoses = response.required_poses;
    state.acceptedPerPose = response.accepted_per_pose;
    state.remainingPerPose = response.remaining_per_pose;
    state.nextPose = response.required_poses[0] ?? null;
    state.progressPercent = 0;
    state.captureStatus = "idle";
    state.uiHint = "Enrollment started. Follow the first pose and capture a frame.";
    elements.result.textContent = JSON.stringify(response, null, 2);
    updateMetrics(null);
    renderWizard();
    setOverlay("Enrollment ready", "idle");
  } catch (error) {
    state.captureStatus = "rejected";
    state.uiHint = String(error);
    renderWizard();
    setOverlay("Start failed", "rejected");
    elements.result.textContent = JSON.stringify({ error: String(error) }, null, 2);
  } finally {
    elements.startButton.disabled = false;
  }
}

async function captureEnrollmentFrame() {
  if (!state.enrollmentSessionId) {
    return;
  }
  const pose = currentPose();
  if (!pose) {
    return;
  }
  try {
    state.captureStatus = "validating";
    state.uiHint = "Checking pose, lighting, liveness, and sharpness...";
    renderWizard();
    setOverlay(`Validating ${poseTitle(pose)}...`, "validating");
    const response = await postJson("/enroll/frame", {
      enrollment_session_id: state.enrollmentSessionId,
      device_code: DEVICE_CODE,
      pose,
      frame_b64: captureSingleFrame(),
    });
    state.remainingPerPose = response.remaining_per_pose;
    state.nextPose = response.next_pose;
    state.progressPercent = response.progress_percent;
    state.captureStatus = response.capture_status;
    state.uiHint = response.ui_hint;
    updateMetrics(response.quality);
    elements.result.textContent = JSON.stringify(response, null, 2);
    renderWizard();
    setOverlay(response.accepted ? "Frame accepted" : "Frame rejected", response.accepted ? "accepted" : "rejected");
  } catch (error) {
    state.captureStatus = "rejected";
    state.uiHint = String(error);
    renderWizard();
    setOverlay("Capture failed", "rejected");
    elements.result.textContent = JSON.stringify({ error: String(error) }, null, 2);
  }
}

async function finishEnrollment() {
  if (!state.enrollmentSessionId) {
    return;
  }
  try {
    state.captureStatus = "validating";
    state.uiHint = "Building face template from accepted samples...";
    renderWizard();
    setOverlay("Finalizing enrollment...", "validating");
    const response = await postJson("/enroll/finish", { enrollment_session_id: state.enrollmentSessionId });
    state.captureStatus = "completed";
    state.uiHint = "Enrollment complete. The person is now active for attendance.";
    state.progressPercent = 100;
    elements.result.textContent = JSON.stringify(response, null, 2);
    renderWizard();
    setOverlay("Enrollment completed", "accepted");
  } catch (error) {
    state.captureStatus = "rejected";
    state.uiHint = String(error);
    renderWizard();
    setOverlay("Finish failed", "rejected");
    elements.result.textContent = JSON.stringify({ error: String(error) }, null, 2);
  }
}

async function runRecognitionBurst() {
  try {
    setOverlay("Capturing recognition burst...", "validating");
    const response = await postJson("/recognize", {
      device_code: DEVICE_CODE,
      frames: await captureBurst(),
      session_code: null,
    });
    elements.recognitionResult.textContent = JSON.stringify(response, null, 2);
    setOverlay("Recognition completed", "accepted");
  } catch (error) {
    elements.recognitionResult.textContent = JSON.stringify({ error: String(error) }, null, 2);
    setOverlay("Recognition failed", "rejected");
  }
}

async function startCamera() {
  const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
  elements.camera.srcObject = stream;
  elements.status.textContent = JSON.stringify({ camera: "ready", tracks: stream.getVideoTracks().length, device_code: DEVICE_CODE }, null, 2);
  setOverlay("Camera ready", "idle");
}

elements.startForm.addEventListener("submit", startEnrollment);
elements.captureButton.addEventListener("click", captureEnrollmentFrame);
elements.finishButton.addEventListener("click", finishEnrollment);
elements.recognitionButton.addEventListener("click", runRecognitionBurst);
elements.enrollModeButton.addEventListener("click", () => setMode("enroll"));
elements.recognizeModeButton.addEventListener("click", () => setMode("recognize"));

renderWizard();
setMode("enroll");
startCamera().catch((error) => {
  elements.status.textContent = JSON.stringify({ error: String(error) }, null, 2);
  setOverlay("Camera unavailable", "rejected");
});
