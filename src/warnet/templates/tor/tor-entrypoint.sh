#!/bin/bash
set -e

echo "Address $(ip addr show eth0 | grep "inet\b" | awk '{print $2}' | cut -d/ -f1)" >> /etc/tor/torrc
# mkdir -p /home/debian-tor/.tor/keys
# chown -R debian-tor:debian-tor /home/debian-tor
gosu debian-tor tor -f /etc/tor/torrc
