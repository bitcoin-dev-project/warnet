#!/bin/bash

# DNS server IP and the hostname to query
DNS_SERVER="dummySeed.invalid"
HOSTNAME="x9.dummySeed.invalid"

# Maximum number of retries
MAX_RETRIES=100
RETRY_COUNT=0
SLEEP=1

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  RETRY_COUNT=$((RETRY_COUNT+1))
 
  # Query the DNS server and check for any lines in the "ANSWER SECTION" with an IP address
  if dig @$DNS_SERVER $HOSTNAME +noall +answer | grep -qE 'IN\s+A\s+\b([0-9]{1,3}\.){3}[0-9]{1,3}\b'; then
    echo "Got response from DNS server"
    exit 0
  else
    sleep $SLEEP
  fi
done

# If we reach here, we exhausted the maximum retries, but we want to continue startup anyway
echo "No response from DNS server after $MAX_RETRIES with $SLEEP seconds delay. Continuing"
exit 0
