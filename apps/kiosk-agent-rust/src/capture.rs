use anyhow::Result;
use tokio::fs;

pub struct FilesystemFrameSource {
    path: String,
}

impl FilesystemFrameSource {
    pub fn new(path: String) -> Self {
        Self { path }
    }

    pub async fn capture_frame(&self) -> Result<Vec<u8>> {
        Ok(fs::read(&self.path).await?)
    }
}

