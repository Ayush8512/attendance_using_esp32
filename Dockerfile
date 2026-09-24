FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for dlib and face_recognition
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .

# Restrict CMake to 1 core to prevent "Out of memory" errors on Render when compiling dlib
ENV CMAKE_BUILD_PARALLEL_LEVEL=1

RUN pip install --no-cache-dir dlib==19.24.2 || true
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

WORKDIR /app/backend

# Expose port
EXPOSE 10000

# Start server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
