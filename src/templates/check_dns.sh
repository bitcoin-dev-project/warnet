#!/bin/bash

# DNS server IP and the hostname to query
DNS_SERVER="dummySeed.invalid"
HOSTNAME="x9.dummySeed.invalid"

# Maximum number of retries
MAX_RETRIES=100
RETRY_COUNT=0
SLEEP=1

# Loop until maximum retries reached
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  # Increment the retry count
  RETRY_COUNT=$((RETRY_COUNT+1))
  
  # Query the DNS server and store the answer section in a variable
  RESPONSE=$(dig @$DNS_SERVER $HOSTNAME +noall +answer)

  # Check if the response contains any IP addresses
  if echo "$RESPONSE" | grep -qE 'IN\s+A\s+\b([0-9]{1,3}\.){3}[0-9]{1,3}\b'; then
    echo "Received valid DNS response:"
    echo "$RESPONSE"
    exit 0
  else
    sleep $SLEEP
  fi
done

# If we reach here, we exhausted the maximum retries, but we want to continue startup anyway
echo "No response from DNS server after $MAX_RETRIES with $SLEEP seconds delay. Continuing"
exit 0
