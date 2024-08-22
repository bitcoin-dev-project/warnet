# Use an official Python runtime as the base image
FROM python:3.12-slim

# Python dependencies
#RUN pip install --no-cache-dir prometheus_client

# Prometheus exporter script for bitcoind
COPY src/warnet/scenarios/commander.py /
COPY src/test_framework /test_framework

# -u: force the stdout and stderr streams to be unbuffered
ENTRYPOINT ["python", "-u", "/scenario.py"]
