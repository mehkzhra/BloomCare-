FROM node:24-alpine AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements*.txt backend/research-requirements.txt /app/backend/
COPY ml/requirements.txt /app/ml/requirements.txt
RUN python -m pip install --no-cache-dir -r backend/requirements.txt -r backend/research-requirements.txt
COPY backend/ /app/backend/
# Only source is copied: PE runtime assets are mounted privately by the host.
COPY ml/*.py /app/ml/
COPY deploy/prepare_cloud_model.py deploy/start_cloud.py /app/deploy/
COPY --from=frontend /web/dist/ /app/frontend/dist/
RUN python deploy/prepare_cloud_model.py --maternal-only
RUN mkdir -p /app/ml/artifacts/legacy_pe_v0.7.1 && useradd --create-home bloomcare && chown -R bloomcare:bloomcare /app
USER bloomcare
WORKDIR /app/backend
EXPOSE 10000
CMD ["python", "/app/deploy/start_cloud.py"]
