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

/// Owns the camera on a dedicated OS thread and answers frame requests over a
/// channel.
///
/// `nokhwa::Camera` holds a `dyn CaptureBackendTrait` that is neither `Send` nor
/// `Sync`, so it cannot live inside a `FrameSource` (which must be both) nor be
/// held across an await point. Confining it to one thread that never hands the
/// camera out sidesteps that entirely, and blocking driver calls stay off the
/// async runtime as a bonus.
#[cfg(feature = "camera")]
pub struct CameraFrameSource {
    requests: tokio::sync::mpsc::UnboundedSender<FrameReply>,
}

#[cfg(feature = "camera")]
type FrameReply = tokio::sync::oneshot::Sender<Result<Vec<u8>>>;

#[cfg(feature = "camera")]
impl CameraFrameSource {
    pub fn new(index: u32, width: u32, height: u32, fps: u32) -> Result<Self> {
        let (request_tx, mut request_rx) = tokio::sync::mpsc::unbounded_channel::<FrameReply>();
        // Opening the device happens on the worker thread, but the caller still
        // needs to learn whether it succeeded, hence this one-shot handshake.
        let (ready_tx, ready_rx) = std::sync::mpsc::channel::<Result<()>>();

        std::thread::Builder::new()
            .name("kiosk-camera".to_string())
            .spawn(move || match open_camera(index, width, height, fps) {
                Err(error) => {
                    let _ = ready_tx.send(Err(error));
                }
                Ok(mut camera) => {
                    let _ = ready_tx.send(Ok(()));
                    while let Some(reply) = request_rx.blocking_recv() {
                        // A dropped receiver just means the caller gave up.
                        let _ = reply.send(grab_jpeg(&mut camera));
                    }
                }
            })?;

        ready_rx
            .recv()
            .map_err(|_| anyhow::anyhow!("camera thread stopped before reporting readiness"))??;

        Ok(Self {
            requests: request_tx,
        })
    }
}

#[cfg(feature = "camera")]
fn open_camera(index: u32, width: u32, height: u32, fps: u32) -> Result<nokhwa::Camera> {
    use nokhwa::pixel_format::RgbFormat;
    use nokhwa::utils::{
        CameraFormat, CameraIndex, FrameFormat, RequestedFormat, RequestedFormatType, Resolution,
    };

    // Closest() honours the requested resolution and frame rate instead of
    // discarding them the way HighestFrameRate() did.
    let wanted = CameraFormat::new(
        Resolution::new(width.max(1), height.max(1)),
        FrameFormat::MJPEG,
        fps.clamp(1, 60),
    );
    let mut camera = nokhwa::Camera::new(
        CameraIndex::Index(index),
        RequestedFormat::new::<RgbFormat>(RequestedFormatType::Closest(wanted)),
    )?;
    camera.open_stream()?;
    Ok(camera)
}

#[cfg(feature = "camera")]
fn grab_jpeg(camera: &mut nokhwa::Camera) -> Result<Vec<u8>> {
    use nokhwa::pixel_format::RgbFormat;
    use nokhwa::utils::FrameFormat;

    let buffer = camera.frame()?;
    // MJPEG streams are already JPEG on the wire; re-encoding would only cost
    // time and a generation of quality.
    if buffer.source_frame_format() == FrameFormat::MJPEG {
        return Ok(buffer.buffer().to_vec());
    }

    let resolution = buffer.resolution();
    let (width, height) = (resolution.width(), resolution.height());
    let mut rgb = vec![0_u8; width as usize * height as usize * 3];
    buffer.decode_image_to_buffer::<RgbFormat>(&mut rgb)?;

    let mut jpeg = Vec::new();
    image::codecs::jpeg::JpegEncoder::new(&mut jpeg).encode(
        &rgb,
        width,
        height,
        image::ExtendedColorType::Rgb8,
    )?;
    Ok(jpeg)
}

#[cfg(feature = "camera")]
#[async_trait]
impl FrameSource for CameraFrameSource {
    async fn capture_frame(&self) -> Result<Vec<u8>> {
        let (reply_tx, reply_rx) = tokio::sync::oneshot::channel();
        self.requests
            .send(reply_tx)
            .map_err(|_| anyhow::anyhow!("camera thread is no longer running"))?;
        reply_rx
            .await
            .map_err(|_| anyhow::anyhow!("camera thread dropped the frame request"))?
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

