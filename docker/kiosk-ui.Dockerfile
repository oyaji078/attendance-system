FROM python:3.11-slim

WORKDIR /app

COPY apps/kiosk-ui ./apps/kiosk-ui

CMD ["python", "-m", "http.server", "8080", "--directory", "apps/kiosk-ui/src"]

