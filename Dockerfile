FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y sqlite3 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/data
ENV DATABASE_PATH=/app/data/planner.db
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]
