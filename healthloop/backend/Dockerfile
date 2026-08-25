# Hugging Face Spaces (Docker SDK) deployment for HealthLoop backend

FROM python:3.11-slim

# Install Tesseract OCR (system dependency, needed for report photo reading)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Hugging Face Spaces (Docker SDK) expects the app to listen on port 7860
EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
