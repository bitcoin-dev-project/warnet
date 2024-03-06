#!/bin/bash
set -e

echo "Address $(ip addr show eth0 | grep "inet\b" | awk '{print $2}' | cut -d/ -f1)" >> /etc/tor/torrc
tor --verify-config
tor -f /etc/tor/torrc