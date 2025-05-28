#!/usr/bin/env python3

from pathlib import Path

from warnet.process import run_command

if __name__ == "__main__":
    command = f"helm upgrade --install torda {Path(__file__).parent / 'charts' / 'torda'}"
    run_command(command)
