#!/bin/bash

# Generate the private key using the P-256 curve
openssl ecparam -name prime256v1 -genkey -noout -out tls.key

# Generate the self-signed certificate using the configuration file
# Expires in ten years, 2034
openssl req -x509 -new -nodes -key tls.key -days 3650 -out tls.cert -config openssl-config.cnf
