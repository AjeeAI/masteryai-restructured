FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY ai_core/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY ai_core /app/ai_core

EXPOSE 10000

CMD ["sh", "-c", "uvicorn ai_core.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
