use anyhow::Result;
use async_trait::async_trait;
use tokio::fs;

#[async_trait]
pub trait FrameSource: Send + Sync {
    async fn capture_frame(&self) -> Result<Vec<u8>>;
}

pub struct FilesystemFrameSource {
    path: String,
}

impl FilesystemFrameSource {
    pub fn new(path: String) -> Self {
        Self { path }
    }
}

#[async_trait]
impl FrameSource for FilesystemFrameSource {
    async fn capture_frame(&self) -> Result<Vec<u8>> {
        Ok(fs::read(&self.path).await?)
    }
}

#[cfg(feature = "camera")]
pub struct CameraFrameSource {
    camera: tokio::sync::Mutex<nokhwa::Camera>,
}

#[cfg(feature = "camera")]
impl CameraFrameSource {
    pub fn new(index: u32, _width: u32, _height: u32, fps: u32) -> Result<Self> {
        use nokhwa::utils::{CameraIndex, RequestedFormat, RequestedFormatType, MJPEGFormat};
        let camera = nokhwa::Camera::new(
            CameraIndex::Index(index),
            RequestedFormat::new::<MJPEGFormat>(RequestedFormatType::HighestFrameRate(
                fps.max(1).min(60),
            )),
        )?;
        Ok(Self {
            camera: tokio::sync::Mutex::new(camera),
        })
    }
}

#[cfg(feature = "camera")]
#[async_trait]
impl FrameSource for CameraFrameSource {
    async fn capture_frame(&self) -> Result<Vec<u8>> {
        let mut cam = self.camera.lock().await;
        let frame = cam.frame()?;
        let buf = frame.buffer().to_vec();
        if buf.len() > 2 && buf[0] == 0xFF && buf[1] == 0xD8 {
            return Ok(buf);
        }
        let resolution = frame.resolution();
        let width = resolution.width() as u32;
        let height = resolution.height() as u32;
        let img = image::RgbImage::from_raw(width, height, buf)
            .ok_or_else(|| anyhow::anyhow!("invalid camera buffer dimensions {}x{} len={}", width, height, buf.len()))?;
        let mut jpeg = Vec::new();
        let mut encoder = image::codecs::jpeg::JpegEncoder::new(&mut jpeg);
        encoder.encode(img.as_raw(), img.width(), img.height(), image::ExtendedColorType::Rgb8)?;
        Ok(jpeg)
    }
}

#[derive(Clone, Debug)]
pub enum FrameSourceKind {
    Filesystem(String),
    #[cfg(feature = "camera")]
    Camera { index: u32, width: u32, height: u32, fps: u32 },
}

pub fn create_frame_source(kind: FrameSourceKind) -> Result<Box<dyn FrameSource>> {
    match kind {
        FrameSourceKind::Filesystem(path) => Ok(Box::new(FilesystemFrameSource::new(path))),
        #[cfg(feature = "camera")]
        FrameSourceKind::Camera { index, width, height, fps } => {
            Ok(Box::new(CameraFrameSource::new(index, width, height, fps)?))
        }
    }
}

