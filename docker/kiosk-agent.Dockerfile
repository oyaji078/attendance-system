FROM rust:1.81-slim AS builder

WORKDIR /workspace

COPY apps/kiosk-agent-rust ./apps/kiosk-agent-rust

WORKDIR /workspace/apps/kiosk-agent-rust
RUN cargo build --release

FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /workspace/apps/kiosk-agent-rust/target/release/kiosk-agent-rust /usr/local/bin/kiosk-agent-rust

CMD ["kiosk-agent-rust"]
