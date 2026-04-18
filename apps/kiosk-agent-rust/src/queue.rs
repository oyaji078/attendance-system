use std::collections::VecDeque;

use crate::models::RecognizeRequest;

#[derive(Default)]
pub struct LocalQueue { items: VecDeque<RecognizeRequest> }

impl LocalQueue {
    pub fn push(&mut self, request: RecognizeRequest) { self.items.push_back(request); }
    pub fn pop(&mut self) -> Option<RecognizeRequest> { self.items.pop_front() }
    pub fn len(&self) -> usize { self.items.len() }
}

