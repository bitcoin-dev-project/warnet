#!/bin/bash

if pgrep -f warnet > /dev/null; then
    exit 0
else
    exit 1
fi
