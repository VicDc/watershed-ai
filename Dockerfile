FROM python:3.12-slim

# Dipendenze di sistema per rasterio/opencv/tesseract (OCR curve di livello)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgdal-dev \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m watershed && chown -R watershed:watershed /app
USER watershed

EXPOSE 8000

CMD ["python", "-m", "app.main", "--help"]
