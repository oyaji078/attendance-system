mod capture;
mod client;
mod config;
mod liveness;
mod models;
mod quality;
mod queue;

use anyhow::Result;
use base64::{engine::general_purpose::STANDARD, Engine as _};
use chrono::Utc;
use tokio::time::{sleep, Duration};
use tracing::{error, info};
use tracing_subscriber::EnvFilter;

use crate::capture::FilesystemFrameSource;
use crate::client::BackendClient;
use crate::config::AgentConfig;
use crate::liveness::heuristic_score;
use crate::models::{DeviceHeartbeat, RecognitionFrame, RecognizeRequest};
use crate::quality::average_brightness;
use crate::queue::LocalQueue;

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt().with_env_filter(EnvFilter::from_default_env()).init();
    let config = AgentConfig::from_env();
    let client = BackendClient::new(config.backend_base_url.clone());
    let frame_source = FilesystemFrameSource::new(config.sample_frame_path.clone());
    let mut queue = LocalQueue::default();

    loop {
        let heartbeat = DeviceHeartbeat {
            device_code: config.device_code.clone(),
            agent_version: env!("CARGO_PKG_VERSION").to_string(),
            queue_depth: queue.len(),
            captured_at: Utc::now().to_rfc3339(),
        };
        if let Err(error) = client.heartbeat(&heartbeat).await { error!("heartbeat_failed: {error}"); }

        match frame_source.capture_frame().await {
            Ok(frame_bytes) => {
                let brightness = average_brightness(&frame_bytes).unwrap_or(0.0);
                if heuristic_score(brightness) >= 0.70 {
                    queue.push(RecognizeRequest {
                        device_code: config.device_code.clone(),
                        session_code: None,
                        frames: vec![
                            RecognitionFrame { frame_b64: STANDARD.encode(&frame_bytes), pose_hint: None },
                            RecognitionFrame { frame_b64: STANDARD.encode(&frame_bytes), pose_hint: None },
                            RecognitionFrame { frame_b64: STANDARD.encode(frame_bytes), pose_hint: None },
                        ],
                    });
                }
            }
            Err(error) => error!("frame_capture_failed: {error}"),
        }

        if let Some(request) = queue.pop() {
            if let Err(error) = client.recognize(&request).await {
                error!("recognize_failed: {error}");
                queue.push(request);
            } else {
                info!("recognize_sent");
            }
        }

        sleep(Duration::from_secs(config.heartbeat_interval_seconds)).await;
    }
}
