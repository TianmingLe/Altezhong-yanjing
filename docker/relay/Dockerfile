FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY docker/relay/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY pc/relay /app

CMD ["python", "/app/relay_server.py", "--host", "0.0.0.0", "--port", "8766", "--demo"]
