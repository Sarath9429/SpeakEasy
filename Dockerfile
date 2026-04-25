# ── SynthSpeak Backend — Dockerfile ────────────────────────────────────────
# NOTE: Render uses render.yaml (buildCommand + startCommand) by default.
# This Dockerfile is here as a fallback / for local Docker testing.
# MediaPipe + OpenCV headless work without a display (safe for containers).

FROM python:3.11-slim

# Install OS-level libs required by OpenCV headless & MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1-mesa-glx \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies first (layer cache friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the source code
COPY . .

# Koyeb exposes port 8080 by default
EXPOSE 8080

# Start the FastAPI server with uvicorn
CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8080"]
