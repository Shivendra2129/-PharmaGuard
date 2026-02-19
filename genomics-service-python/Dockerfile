FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for cyvcf2
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-openssl-dev \
    libssl-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service files
COPY . .

# Copy data directory
COPY ../data /data

ENV PYTHON_HOST=0.0.0.0
ENV PYTHON_PORT=8000

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
