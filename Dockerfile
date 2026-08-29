FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y sqlite3 gosu && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 -U -s /bin/bash appuser
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/data /app/logs /app/app/static/uploads && \
    chown -R appuser:appuser /app /home/appuser && \
    chmod +x /app/scripts/entrypoint.sh
ENV DATABASE_PATH=/app/data/planner.db
EXPOSE 5000
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]
