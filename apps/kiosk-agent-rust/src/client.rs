use anyhow::Result;
use reqwest::Client;

use crate::models::{DeviceHeartbeat, RecognizeRequest};

#[derive(Clone)]
pub struct BackendClient {
    client: Client,
    base_url: String,
}

impl BackendClient {
    pub fn new(base_url: String) -> Self {
        Self { client: Client::new(), base_url }
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

