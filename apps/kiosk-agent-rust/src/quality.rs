use image::ImageReader;

pub fn average_brightness(frame_bytes: &[u8]) -> Option<f32> {
    let image = ImageReader::new(std::io::Cursor::new(frame_bytes)).with_guessed_format().ok()?.decode().ok()?.to_luma8();
    let total: u64 = image.pixels().map(|pixel| pixel[0] as u64).sum();
    let pixel_count = image.width() as u64 * image.height() as u64;
    if pixel_count == 0 { return None; }
    Some(total as f32 / pixel_count as f32)
}

