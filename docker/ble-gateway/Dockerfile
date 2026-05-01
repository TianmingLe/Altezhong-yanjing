FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY docker/ble-gateway/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY docker/ble-gateway/gateway.py /app/gateway.py

CMD ["python", "/app/gateway.py"]
