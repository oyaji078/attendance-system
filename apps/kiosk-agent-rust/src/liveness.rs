pub fn heuristic_score(brightness: f32) -> f32 {
    if brightness < 20.0 { 0.20 } else if brightness > 220.0 { 0.35 } else { 0.75 }
}

