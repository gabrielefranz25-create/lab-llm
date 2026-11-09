FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agente/ agente/
COPY server_mcp/ server_mcp/
RUN useradd --create-home appuser
RUN mkdir -p /app/dati && chown appuser /app/dati
USER appuser
CMD ["python", "-m", "agente"]
