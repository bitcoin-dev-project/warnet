#!/bin/bash

if pidof python > /dev/null; then
    exit 0
fi

exit 1

