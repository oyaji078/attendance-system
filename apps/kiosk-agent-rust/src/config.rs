use std::env;

use crate::capture::FrameSourceKind;

#[derive(Clone, Debug)]
pub struct AgentConfig {
    pub backend_base_url: String,
    pub device_code: String,
    pub session_code: Option<String>,
    pub heartbeat_interval_seconds: u64,
    pub frame_source: FrameSourceKind,
    pub liveness_threshold: f32,
    pub queue_max_size: usize,
    pub retry_base_backoff_ms: u64,
    pub retry_max_backoff_ms: u64,
    pub max_retries: u32,
    pub request_timeout_seconds: u64,
    pub max_queue_age_seconds: u64,
}

fn env_or<T>(key: &str, default: T) -> T
where
    T: std::str::FromStr,
    T::Err: std::fmt::Debug,
{
    env::var(key).ok().and_then(|v| v.parse::<T>().ok()).unwrap_or(default)
}

impl AgentConfig {
    pub fn from_env() -> Self {
        let frame_source = if let Ok(index) = env::var("CAMERA_INDEX").ok().and_then(|v| v.parse::<u32>().ok()) {
            #[cfg(feature = "camera")]
            {
                FrameSourceKind::Camera {
                    index,
                    width: env_or::<u32>("CAMERA_WIDTH", 640),
                    height: env_or::<u32>("CAMERA_HEIGHT", 480),
                    fps: env_or::<u32>("CAMERA_FPS", 15),
                }
            }
            #[cfg(not(feature = "camera"))]
            {
                let _ = index;
                tracing::warn!("CAMERA_INDEX set but camera feature not enabled; falling back to filesystem source");
                FrameSourceKind::Filesystem(
                    env::var("SAMPLE_FRAME_PATH").unwrap_or_else(|_| "./sample-frame.jpg".to_string()),
                )
            }
        } else {
            FrameSourceKind::Filesystem(
                env::var("SAMPLE_FRAME_PATH").unwrap_or_else(|_| "./sample-frame.jpg".to_string()),
            )
        };

        Self {
            backend_base_url: env::var("BACKEND_BASE_URL").unwrap_or_else(|_| "http://127.0.0.1:8000".to_string()),
            device_code: env::var("DEVICE_CODE").unwrap_or_else(|_| "gate-a01".to_string()),
            session_code: env::var("SESSION_CODE").ok().filter(|s| !s.is_empty()),
            heartbeat_interval_seconds: env_or("HEARTBEAT_INTERVAL_SECONDS", 10),
            frame_source,
            liveness_threshold: env_or("LIVENESS_THRESHOLD", 0.70),
            queue_max_size: env_or("QUEUE_MAX_SIZE", 128),
            retry_base_backoff_ms: env_or("RETRY_BASE_BACKOFF_MS", 1_000),
            retry_max_backoff_ms: env_or("RETRY_MAX_BACKOFF_MS", 60_000),
            max_retries: env_or("MAX_RETRIES", 10),
            request_timeout_seconds: env_or("REQUEST_TIMEOUT_SECONDS", 15),
            max_queue_age_seconds: env_or("MAX_QUEUE_AGE_SECONDS", 300),
        }
    }
}
