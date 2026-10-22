FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements*.txt backend/research-requirements.txt /app/backend/
COPY ml/requirements.txt /app/ml/requirements.txt
RUN python -m pip install --no-cache-dir -r backend/requirements.txt -r backend/research-requirements.txt
COPY backend /app/backend
COPY ml /app/ml
RUN useradd --create-home bloomcare && chown -R bloomcare:bloomcare /app
USER bloomcare
WORKDIR /app/backend
EXPOSE 8000
CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log"]
