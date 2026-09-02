mod capture;
mod client;
mod config;
mod liveness;
mod models;
mod quality;
mod queue;

use std::time::Duration;

use anyhow::Result;
use base64::{engine::general_purpose::STANDARD, Engine as _};
use chrono::Utc;
use tokio::signal;
use tokio::time::timeout;
use tracing::{error, info, warn};
use tracing_subscriber::EnvFilter;

use crate::capture::{create_frame_source, FrameSource};
use crate::client::BackendClient;
use crate::config::AgentConfig;
use crate::liveness::heuristic_score;
use crate::models::{DeviceHeartbeat, RecognitionFrame, RecognizeRequest};
use crate::quality::average_brightness;
use crate::queue::{LocalQueue, QueueConfig};

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt().with_env_filter(EnvFilter::from_default_env()).init();
    let config = AgentConfig::from_env();
    let client = BackendClient::new(config.backend_base_url.clone(), config.request_timeout_seconds);
    let frame_source = create_frame_source(config.frame_source.clone())
        .expect("frame source should be created");

    let queue_config = QueueConfig {
        max_size: config.queue_max_size,
        base_backoff_ms: config.retry_base_backoff_ms,
        max_backoff_ms: config.retry_max_backoff_ms,
        max_retries: config.max_retries,
    };
    let mut queue = LocalQueue::new(queue_config);

    let tick = Duration::from_secs(config.heartbeat_interval_seconds);
    let mut tick_interval = tokio::time::interval(tick);
    tick_interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);

    info!("kiosk_agent_started device_code={} backend={}", config.device_code, config.backend_base_url);

    loop {
        tokio::select! {
            _ = tick_interval.tick() => {
                run_tick(&config, &client, frame_source.as_ref(), &mut queue).await;
            }
            _ = shutdown_signal() => {
                info!("kiosk_agent_shutdown queue_depth={}", queue.len());
                drain_queue(&client, &mut queue).await;
                info!("kiosk_agent_stopped");
                break;
            }
        }
    }

    Ok(())
}

/// Upper bound on sends per tick. Without it a tick could run for minutes after
/// an outage; with only one send per tick the queue could never shrink, because
/// every tick also enqueues a fresh frame.
const MAX_SENDS_PER_TICK: usize = 8;

async fn run_tick(config: &AgentConfig, client: &BackendClient, frame_source: &dyn FrameSource, queue: &mut LocalQueue) {
    heartbeat(client, config, queue.len()).await;

    capture_and_enqueue(config, frame_source, queue).await;

    for _ in 0..MAX_SENDS_PER_TICK {
        let Some(item) = queue.pop_ready() else { break };
        match client.recognize(&item.request).await {
            Ok(()) => {
                info!("recognize_sent queue_depth={}", queue.len());
            }
            Err(error) => {
                error!("recognize_failed retry={}/{} error={error}", item.retry_count + 1, config.max_retries);
                if !queue.push_back(item) {
                    warn!("recognize_dropped max_retries_exceeded_or_queue_full");
                }
                // Back off the whole tick rather than hammering a backend that
                // just failed; the next tick retries.
                break;
            }
        }
    }

    let dropped = queue.drop_stale(Duration::from_secs(config.max_queue_age_seconds));
    if dropped > 0 {
        warn!("queue_dropped_stale count={dropped}");
    }
}

async fn heartbeat(client: &BackendClient, config: &AgentConfig, queue_depth: usize) {
    let payload = DeviceHeartbeat {
        device_code: config.device_code.clone(),
        agent_version: env!("CARGO_PKG_VERSION").to_string(),
        // Was hardcoded to 0, so a backlogged agent still looked healthy.
        queue_depth,
        captured_at: Utc::now().to_rfc3339(),
    };
    if let Err(error) = client.heartbeat(&payload).await {
        error!("heartbeat_failed: {error}");
    }
}

async fn capture_and_enqueue(config: &AgentConfig, frame_source: &dyn FrameSource, queue: &mut LocalQueue) {
    if queue.is_full() {
        warn!("capture_skipped queue_full size={}", queue.len());
        return;
    }
    let frame_bytes = match frame_source.capture_frame().await {
        Ok(bytes) => bytes,
        Err(error) => {
            error!("frame_capture_failed: {error}");
            return;
        }
    };
    let brightness = average_brightness(&frame_bytes).unwrap_or(0.0);
    let liveness = heuristic_score(brightness);
    if liveness < config.liveness_threshold {
        // Silently dropping these made "nothing is being sent" impossible to
        // diagnose in the field.
        info!(
            "frame_rejected reason=liveness_below_threshold score={liveness:.2} threshold={:.2} brightness={brightness:.1}",
            config.liveness_threshold
        );
        return;
    }
    let frame_b64 = STANDARD.encode(&frame_bytes);
    let request = RecognizeRequest {
        device_code: config.device_code.clone(),
        session_code: config.session_code.clone(),
        frames: vec![RecognitionFrame { frame_b64, pose_hint: None }],
    };
    if !queue.push(request) {
        warn!("enqueue_failed queue_full");
    }
}

async fn drain_queue(client: &BackendClient, queue: &mut LocalQueue) {
    let deadline = tokio::time::Instant::now() + Duration::from_secs(5);
    while let Some(item) = queue.pop_ready() {
        if tokio::time::Instant::now() >= deadline {
            warn!("drain_timeout remaining={}", queue.len());
            break;
        }
        match timeout(Duration::from_secs(3), client.recognize(&item.request)).await {
            Ok(Ok(())) => info!("drain_sent"),
            Ok(Err(error)) => {
                error!("drain_failed: {error}");
                if !queue.push_back(item) {
                    break;
                }
            }
            Err(_) => {
                error!("drain_timeout");
                if !queue.push_back(item) {
                    break;
                }
            }
        }
    }
}

#[cfg(unix)]
async fn shutdown_signal() {
    // `signal(..)` returns a Result whose Ok value is the stream; the previous
    // `term.ok()` handed select! an Option, which is not a future and so never
    // compiled on Unix at all.
    let mut term = match signal::unix::signal(signal::unix::SignalKind::terminate()) {
        Ok(stream) => stream,
        Err(error) => {
            warn!("sigterm_handler_unavailable: {error}");
            signal::ctrl_c().await.ok();
            return;
        }
    };
    tokio::select! {
        _ = signal::ctrl_c() => {}
        _ = term.recv() => {}
    }
}

#[cfg(not(unix))]
async fn shutdown_signal() {
    signal::ctrl_c().await.ok();
}
