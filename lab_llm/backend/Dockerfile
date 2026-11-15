# Immagine del back-end (lezione 6, step 9): build dalla cartella lab_llm/
#   docker compose build backend
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ backend/
RUN useradd --create-home appuser
USER appuser
CMD ["python", "-m", "backend"]
