const camera = document.getElementById("camera");
const captureButton = document.getElementById("capture");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");

async function startCamera() {
  const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
  camera.srcObject = stream;
  statusEl.textContent = JSON.stringify({ camera: "ready", tracks: stream.getVideoTracks().length }, null, 2);
}

function captureSingleFrame() {
  const canvas = document.createElement("canvas");
  canvas.width = camera.videoWidth || 640;
  canvas.height = camera.videoHeight || 480;
  const context = canvas.getContext("2d");
  context.drawImage(camera, 0, 0, canvas.width, canvas.height);
  return { frame_b64: canvas.toDataURL("image/jpeg", 0.9).split(",")[1], pose_hint: null };
}

async function captureBurst() {
  const frames = [];
  for (let index = 0; index < 3; index += 1) {
    frames.push(captureSingleFrame());
    await new Promise((resolve) => setTimeout(resolve, 120));
  }
  return frames;
}

captureButton.addEventListener("click", async () => {
  try {
    const response = await fetch("http://localhost:8000/recognize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_code: "web-kiosk-a01", frames: await captureBurst(), session_code: null }),
    });
    resultEl.textContent = JSON.stringify(await response.json(), null, 2);
  } catch (error) {
    resultEl.textContent = JSON.stringify({ error: String(error) }, null, 2);
  }
});

startCamera().catch((error) => {
  statusEl.textContent = JSON.stringify({ error: String(error) }, null, 2);
});

