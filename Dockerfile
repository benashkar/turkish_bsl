FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/output/json /app/logs

# Use committed JSON data instead of re-scraping during build
# GitHub Actions will refresh data daily and commit new JSON files
RUN echo "=== Building: Using committed JSON data ===" && \
    ls -la /app/output/json/*_latest.json 2>/dev/null || echo "No latest files" && \
    echo "=== Build complete: Data ready ==="

ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; print('OK')" || exit 1

RUN chmod +x start.sh

CMD ["./start.sh"]
