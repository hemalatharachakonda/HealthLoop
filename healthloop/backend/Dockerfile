# Render (Docker runtime) deployment for HealthLoop backend

FROM python:3.11-slim

# pytesseract needs the tesseract-ocr binary; pdf2image needs poppler-utils.
# Neither is installable via pip - Render's plain "Python" runtime only ever runs
# `pip install`, it never apt-installs system packages. That's why OCR/PDF reading
# fails until this service's Environment is switched to Docker in Render's settings.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render assigns the port dynamically via $PORT - do NOT hardcode a port here.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
