# Multi-stage Open-Source Container Image for UX-mAInd Studio (US-75)
FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
COPY docs/ /build/docs/
RUN mkdir -p /build/ux_maind/app/web/generated && node build.mjs

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LITELLM_LOCAL_MODEL_COST_MAP=True

RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer-nogui \
    libreoffice-impress-nogui \
    libreoffice-calc-nogui \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE* AGENTS.md ./
COPY ux_maind/ ./ux_maind/
COPY docs/ ./docs/
COPY --from=frontend-builder /build/ux_maind/app/web/generated/ ./ux_maind/app/web/generated/

RUN pip install --no-cache-dir -e . && mkdir -p /data/workspace

EXPOSE 8465
VOLUME ["/data/workspace"]
CMD ["ux-maind", "--port", "8465", "--workspace", "/data/workspace", "--no-browser"]
