# ExoSeer backend — FastAPI + scientific engine, packaged for Hugging Face Spaces (Docker SDK).
#
# HF Spaces routes public traffic to the port declared as `app_port` in README_SPACE.md
# (7860 here), so uvicorn binds 0.0.0.0:7860 and the image EXPOSEs 7860.
#
# The heavy scientific stack (lightkurve, transitleastsquares, numba, batman-package,
# astropy, astroquery, xgboost, shap) needs a C/Fortran toolchain to build wheels, and
# xgboost's runtime needs OpenMP (libgomp1). Those are installed via apt below.
FROM python:3.11-slim

# Fail fast and unbuffer stdout so build/run logs stream to the Space console.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build toolchain + runtime libs:
#   build-essential, gcc, gfortran -> compile numba/batman/scipy extensions
#   libgomp1                       -> OpenMP runtime required by xgboost on Linux
# Clean the apt lists afterwards to keep the image small.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        gfortran \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so this layer is cached across app-code changes.
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the application, the vendored trained model, and the vendored NASA tables.
# models/ and data/ ship in the image so no large downloads happen at container boot.
COPY app ./app
COPY models ./models
COPY data ./data

# On-disk light-curve cache. EXOSEER_CACHE_DIR points the engine here; mount a
# volume at this path (see docker-compose.yml) to persist downloads across restarts.
ENV EXOSEER_CACHE_DIR=/app/cache
RUN mkdir -p /app/cache

# HF Spaces (Docker SDK) expects the container to listen on 7860.
EXPOSE 7860

# Liveness probe hits the FastAPI health endpoint (AGENTS.md §8).
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,sys,os; p=os.environ.get('PORT','7860'); sys.exit(0) if urllib.request.urlopen(f'http://127.0.0.1:{p}/healthz', timeout=5).status == 200 else sys.exit(1)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
