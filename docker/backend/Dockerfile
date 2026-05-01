FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY docker/backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY omi/backend /app
COPY docker/backend/entrypoint.sh /app/entrypoint.sh

ENTRYPOINT ["sh", "/app/entrypoint.sh"]
