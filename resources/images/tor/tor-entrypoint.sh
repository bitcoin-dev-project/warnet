#!/bin/bash
set -e

V3IDENT=D9ED7BC69543F1477968C312E7EEEB933BC4EF6D

echo "Starting tor-entrypoint.sh"

IP_ADDR=$(ip addr show eth0 | grep "inet\b" | awk '{print $2}' | cut -d/ -f1)

until TORDA_IP=$(dig +short torda.default.svc.cluster.local); do
  echo "Waiting for DNS: torda"
  sleep 2
done

echo "My IP address: $IP_ADDR"
echo "Directory Authority IP address: $TORDA_IP"

echo "Address $IP_ADDR" >> /etc/tor/torrc
echo "DirAuthority orport=9001 no-v2 v3ident=$V3IDENT $TORDA_IP:9030 03E942A4F12D85B2CF7CBA4E910F321AE98EC233" >> /etc/tor/torrc

cat /etc/tor/torrc

su -s /bin/sh debian-tor -c 'tor'
