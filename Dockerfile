FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CONFIG_DIR=/app/config \
    HOST=0.0.0.0 \
    PORT=7777

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN mkdir -p /app/config

EXPOSE 7777

CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST} --port ${PORT}"]
