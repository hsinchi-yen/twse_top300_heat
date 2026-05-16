FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

CMD ["sh", "-c", "python seed.py && uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-1} --timeout-keep-alive ${UVICORN_KEEPALIVE_SECONDS:-5} --log-level ${UVICORN_LOG_LEVEL:-warning}"]
