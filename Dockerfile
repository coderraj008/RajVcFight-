FROM python:3.13-slim

# ================= SYSTEM DEPENDENCIES =================
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    build-essential \
    python3-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# ================= WORKDIR =================
WORKDIR /app

# ================= PIP UPDATE =================
RUN pip install --upgrade pip setuptools wheel

# ================= INSTALL DEPENDENCIES =================
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# ================= COPY PROJECT =================
COPY . .

# ================= RUN =================
CMD ["python", "main.py"]
