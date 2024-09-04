# Use an official Python runtime as the base image
FROM python:3.12-slim

# Python dependencies
#RUN pip install --no-cache-dir prometheus_client

# The directory will contain the commander's executable
RUN mkdir /wbin

COPY resources/scenarios/commander.py /
COPY src/test_framework /test_framework
COPY resources/images/commander/entrypoint.sh /
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
