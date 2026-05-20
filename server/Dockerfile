# Multi-stage build for RAG-Anything OCR Service
FROM python:3.10-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Fix Docker DNS: inject Google DNS before apt-get
RUN cp /etc/resolv.conf /etc/resolv.conf.bak; \
    echo "nameserver 8.8.8.8" > /tmp/resolv.conf; \
    echo "nameserver 8.8.4.4" >> /tmp/resolv.conf; \
    cp /tmp/resolv.conf /etc/resolv.conf 2>/dev/null || true; \
    apt-get -o Acquire::Retries=5 \
            -o Acquire::http::Pipeline-Depth=0 \
            -o Acquire::http::Timeout=60 \
            update && \
    apt-get -o Acquire::Retries=5 \
            -o Acquire::http::Pipeline-Depth=0 \
            -o Acquire::http::Timeout=60 \
            install -y --no-install-recommends --fix-missing \
    libreoffice \
    poppler-utils \
    tesseract-ocr tesseract-ocr-vie tesseract-ocr-eng \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 \
    libxcb1 libxkbcommon-x11-0 libxcb-cursor0 \
    curl wget gcc g++ && \
    rm -rf /var/lib/apt/lists/*; \
    cp /etc/resolv.conf.bak /etc/resolv.conf 2>/dev/null || true

# Set working directory
WORKDIR /app

# Copy base requirements (HEAVY - cached, rarely changes)
COPY requirements.txt .

# Install base dependencies (cached layer ~500MB)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy extra requirements (LIGHT - add new packages here)
COPY requirements-extra.txt .

# Install extra dependencies (small layer, fast rebuild ~30s)
RUN pip install --no-cache-dir -r requirements-extra.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p storage logs && \
    chmod -R 755 storage logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]