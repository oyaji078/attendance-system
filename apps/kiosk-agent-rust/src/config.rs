use std::env;

#[derive(Clone, Debug)]
pub struct AgentConfig {
    pub backend_base_url: String,
    pub device_code: String,
    pub heartbeat_interval_seconds: u64,
    pub sample_frame_path: String,
}

impl AgentConfig {
    pub fn from_env() -> Self {
        Self {
            backend_base_url: env::var("BACKEND_BASE_URL").unwrap_or_else(|_| "http://127.0.0.1:8000".to_string()),
            device_code: env::var("DEVICE_CODE").unwrap_or_else(|_| "gate-a01".to_string()),
            heartbeat_interval_seconds: env::var("HEARTBEAT_INTERVAL_SECONDS").ok().and_then(|v| v.parse::<u64>().ok()).unwrap_or(10),
            sample_frame_path: env::var("SAMPLE_FRAME_PATH").unwrap_or_else(|_| "./sample-frame.jpg".to_string()),
        }
    }
}

