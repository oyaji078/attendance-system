use std::collections::VecDeque;
use std::time::{Duration, Instant};

use crate::models::RecognizeRequest;

const DEFAULT_MAX_QUEUE_SIZE: usize = 128;
const DEFAULT_BASE_BACKOFF_MS: u64 = 1_000;
const DEFAULT_MAX_BACKOFF_MS: u64 = 60_000;
const DEFAULT_MAX_RETRIES: u32 = 10;

#[derive(Clone)]
pub struct QueueConfig {
    pub max_size: usize,
    pub base_backoff_ms: u64,
    pub max_backoff_ms: u64,
    pub max_retries: u32,
}

impl Default for QueueConfig {
    fn default() -> Self {
        Self {
            max_size: DEFAULT_MAX_QUEUE_SIZE,
            base_backoff_ms: DEFAULT_BASE_BACKOFF_MS,
            max_backoff_ms: DEFAULT_MAX_BACKOFF_MS,
            max_retries: DEFAULT_MAX_RETRIES,
        }
    }
}

#[derive(Clone)]
pub struct QueuedItem {
    pub request: RecognizeRequest,
    pub retry_count: u32,
    pub last_attempt_at: Instant,
}

pub struct LocalQueue {
    items: VecDeque<QueuedItem>,
    config: QueueConfig,
}

impl LocalQueue {
    pub fn new(config: QueueConfig) -> Self {
        Self { items: VecDeque::with_capacity(config.max_size), config }
    }

    pub fn push(&mut self, request: RecognizeRequest) -> bool {
        if self.items.len() >= self.config.max_size {
            return false;
        }
        self.items.push_back(QueuedItem {
            request,
            retry_count: 0,
            last_attempt_at: Instant::now(),
        });
        true
    }

    pub fn push_back(&mut self, mut item: QueuedItem) -> bool {
        item.retry_count += 1;
        item.last_attempt_at = Instant::now();
        if item.retry_count > self.config.max_retries {
            return false;
        }
        if self.items.len() >= self.config.max_size {
            return false;
        }
        self.items.push_back(item);
        true
    }

    pub fn pop_ready(&mut self) -> Option<QueuedItem> {
        let now = Instant::now();
        let front = self.items.front()?;
        let backoff = self.backoff_for(front.retry_count);
        if now.saturating_duration_since(front.last_attempt_at) < backoff {
            return None;
        }
        self.items.pop_front()
    }

    pub fn backoff_for(&self, retry_count: u32) -> Duration {
        let ms = self.config.base_backoff_ms.saturating_mul(1u64.saturating_pow(retry_count));
        let jitter = fastrand::u64(0..ms.saturating_div(2));
        Duration::from_millis((ms + jitter).min(self.config.max_backoff_ms))
    }

    pub fn len(&self) -> usize {
        self.items.len()
    }

    pub fn is_full(&self) -> bool {
        self.items.len() >= self.config.max_size
    }

    pub fn drop_stale(&mut self, max_age: Duration) -> usize {
        let before = self.items.len();
        self.items.retain(|item| item.last_attempt_at.elapsed() < max_age);
        before - self.items.len()
    }
}

impl Default for LocalQueue {
    fn default() -> Self {
        Self::new(QueueConfig::default())
    }
}

#[cfg(test)]
mod tests {
    use std::time::Duration;

    use super::*;
    use crate::models::RecognizeRequest;

    fn dummy_request() -> RecognizeRequest {
        RecognizeRequest {
            device_code: "gate-a01".into(),
            frames: vec![],
            session_code: None,
        }
    }

    #[test]
    fn test_push_and_pop_ready() {
        let config = QueueConfig { max_size: 10, base_backoff_ms: 0, max_backoff_ms: 0, max_retries: 3 };
        let mut q = LocalQueue::new(config);
        assert!(q.push(dummy_request()));
        assert_eq!(q.len(), 1);
        let item = q.pop_ready();
        assert!(item.is_some());
        assert_eq!(item.unwrap().retry_count, 0);
        assert!(q.pop_ready().is_none());
    }

    #[test]
    fn test_push_respects_max_size() {
        let config = QueueConfig { max_size: 2, base_backoff_ms: 0, max_backoff_ms: 0, max_retries: 3 };
        let mut q = LocalQueue::new(config);
        assert!(q.push(dummy_request()));
        assert!(q.push(dummy_request()));
        assert!(!q.push(dummy_request()));
        assert_eq!(q.len(), 2);
        assert!(q.is_full());
    }

    #[test]
    fn test_push_back_increments_retry_and_rejects_exhausted() {
        let config = QueueConfig { max_size: 10, base_backoff_ms: 0, max_backoff_ms: 0, max_retries: 2 };
        let mut q = LocalQueue::new(config);
        assert!(q.push(dummy_request()));
        let item = q.pop_ready().unwrap();
        assert!(q.push_back(item));
        let item = q.pop_ready().unwrap();
        assert_eq!(item.retry_count, 1);
        assert!(q.push_back(item));
        let item = q.pop_ready().unwrap();
        assert_eq!(item.retry_count, 2);
        assert!(!q.push_back(item));
    }

    #[test]
    fn test_backoff_exponential() {
        let config = QueueConfig { base_backoff_ms: 100, max_backoff_ms: 10_000, max_retries: 5, ..Default::default() };
        let q = LocalQueue::new(config);
        let b0 = q.backoff_for(0).as_millis();
        let b1 = q.backoff_for(1).as_millis();
        let b2 = q.backoff_for(2).as_millis();
        assert!(b0 >= 100 && b0 <= 150);
        assert!(b1 >= 100 && b1 <= 200);
        assert!(b2 >= 400 && b2 <= 600);
    }

    #[test]
    fn test_backoff_caps_at_max() {
        let config = QueueConfig { base_backoff_ms: 1_000, max_backoff_ms: 5_000, max_retries: 10, ..Default::default() };
        let q = LocalQueue::new(config);
        for retry in 0..8 {
            let ms = q.backoff_for(retry).as_millis();
            assert!(ms <= 5_000, "retry {} backoff {} exceeded max", retry, ms);
        }
    }

    #[test]
    fn test_pop_ready_respects_backoff() {
        let config = QueueConfig { max_size: 10, base_backoff_ms: 10_000, max_backoff_ms: 60_000, max_retries: 3 };
        let mut q = LocalQueue::new(config);
        assert!(q.push(dummy_request()));
        assert!(q.pop_ready().is_none());
    }

    #[test]
    fn test_drop_stale_removes_old_items() {
        let config = QueueConfig { max_size: 10, base_backoff_ms: 0, max_backoff_ms: 0, max_retries: 3 };
        let mut q = LocalQueue::new(config);
        assert!(q.push(dummy_request()));
        assert!(q.push(dummy_request()));
        q.items[0].last_attempt_at = Instant::now() - Duration::from_secs(100);
        let dropped = q.drop_stale(Duration::from_secs(60));
        assert_eq!(dropped, 1);
        assert_eq!(q.len(), 1);
    }

    #[test]
    fn test_drop_stale_removes_nothing_when_fresh() {
        let config = QueueConfig { max_size: 10, base_backoff_ms: 0, max_backoff_ms: 0, max_retries: 3 };
        let mut q = LocalQueue::new(config);
        assert!(q.push(dummy_request()));
        assert!(q.push(dummy_request()));
        let dropped = q.drop_stale(Duration::from_secs(3600));
        assert_eq!(dropped, 0);
        assert_eq!(q.len(), 2);
    }

    #[test]
    fn test_push_returns_false_when_full() {
        let config = QueueConfig { max_size: 0, base_backoff_ms: 0, max_backoff_ms: 0, max_retries: 0 };
        let mut q = LocalQueue::new(config);
        assert!(!q.push(dummy_request()));
        assert_eq!(q.len(), 0);
    }

    #[test]
    fn test_push_back_returns_false_when_full_even_if_not_exhausted() {
        let config = QueueConfig { max_size: 1, base_backoff_ms: 0, max_backoff_ms: 0, max_retries: 5 };
        let mut q = LocalQueue::new(config);
        assert!(q.push(dummy_request()));
        let item = q.pop_ready().unwrap();
        assert!(q.push_back(item));
        assert!(!q.push(dummy_request()));
    }
}
