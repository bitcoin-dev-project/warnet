#!/bin/bash

if [ -f "/tmp/warnet.pid" ]; then
    exit 0
else
    exit 1
fi
