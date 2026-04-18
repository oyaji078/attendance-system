use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceHeartbeat {
    pub device_code: String,
    pub agent_version: String,
    pub queue_depth: usize,
    pub captured_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecognitionFrame {
    pub frame_b64: String,
    pub pose_hint: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecognizeRequest {
    pub device_code: String,
    pub frames: Vec<RecognitionFrame>,
    pub session_code: Option<String>,
}

