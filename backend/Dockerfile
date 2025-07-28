FROM python:3.11-slim

WORKDIR /app

# Only PostgreSQL client (for SQLAlchemy) & dotenv
RUN apt-get update \
    && apt-get install -y libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# install *all* your Python deps, including uvicorn
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# tell Docker (and Cloud Run) we’ll listen on 8080
EXPOSE 8080

# start Uvicorn directly
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]