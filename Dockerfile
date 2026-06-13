FROM python:3.12-slim

# System deps: Tesseract (+Spanish), OpenCV runtime libs, PDF tooling
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-spa \
        libgl1 libglib2.0-0 \
        poppler-utils qpdf \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Health check hits the app's /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import httpx,sys; sys.exit(0 if httpx.get('http://localhost:8000/health').status_code==200 else 1)"

CMD ["uvicorn", "informes_cev_minvu_db.app:app", "--host", "0.0.0.0", "--port", "8000"]
