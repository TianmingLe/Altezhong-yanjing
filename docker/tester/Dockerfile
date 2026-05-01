FROM python:3.11-slim

WORKDIR /repo

ENV PYTHONUNBUFFERED=1

COPY docker/tester/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /repo

CMD ["sh", "/repo/docker/tester/run_tests.sh"]
