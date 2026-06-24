# ── Build stage: install dependencies ────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /home/app/project

# System libraries required to compile some Python packages (lxml, scipy, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libffi-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests first so this layer is cached when only source changes
COPY pyproject.toml requirements.txt* ./

# Install all project dependencies into a dedicated prefix
RUN pip install --no-cache-dir --prefix=/install -e . 2>/dev/null || \
    pip install --no-cache-dir --prefix=/install .

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.13-slim

LABEL maintainer="stock-research"
LABEL description="AI-powered stock research Streamlit app"

WORKDIR /home/app/project

# Lightweight runtime libraries (required by lxml, reportlab, matplotlib)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Bring installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Pre-create data directories so volume mounts land in the right place
# CACHE_DIR resolves to /home/app/.cache  (PROJECT_ROOT = Path(__file__).parent.parent.parent)
# REPORTS_DIR defaults to ./reports      (relative to CWD = /home/app/project)
RUN mkdir -p /home/app/.cache /home/app/project/reports

EXPOSE 8501

# Set PYTHONPATH so 'from src.*' imports resolve correctly
ENV PYTHONPATH=/home/app/project:${PYTHONPATH}

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "src/ui/streamlit_app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
