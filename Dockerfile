# syntax=docker/dockerfile:1
FROM python:3.11.5-slim

# ----- housekeeping -----
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install uv once (small Rust binary) — it will do the rest of the work
RUN pip install --no-cache-dir uv

WORKDIR /app
COPY data ./data

# Install project requirements with uv
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Bring in the rest of your source code
COPY . .

EXPOSE 8080

# Start the FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
