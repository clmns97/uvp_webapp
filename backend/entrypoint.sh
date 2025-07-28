#!/bin/sh
# Load .env variables using python-dotenv, then start FastAPI with Uvicorn on the correct port
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8080}"
