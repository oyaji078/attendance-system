use std::time::Duration;

use anyhow::Result;
use reqwest::Client;

use crate::models::{DeviceHeartbeat, RecognizeRequest};

#[derive(Clone)]
pub struct BackendClient {
    client: Client,
    base_url: String,
}

impl BackendClient {
    pub fn new(base_url: String, timeout_seconds: u64) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(timeout_seconds))
            .pool_max_idle_per_host(2)
            .build()
            .expect("reqwest client should build");
        Self { client, base_url }
    }

    pub async fn heartbeat(&self, payload: &DeviceHeartbeat) -> Result<()> {
        let url = format!("{}/devices/heartbeat/{}", self.base_url, payload.device_code);
        self.client.post(url).json(payload).send().await?.error_for_status()?;
        Ok(())
    }

    pub async fn recognize(&self, payload: &RecognizeRequest) -> Result<()> {
        let url = format!("{}/recognize", self.base_url);
        self.client.post(url).json(payload).send().await?.error_for_status()?;
        Ok(())
    }
}
