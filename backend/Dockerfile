FROM python:3.13-slim

# Install system dependencies: Tesseract OCR for image/screenshot parsing
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all backend source files
COPY . .

# Create the data directory for the SQLite database
RUN mkdir -p /app/data

EXPOSE 8000

# Run uvicorn from /app where main.py lives
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
