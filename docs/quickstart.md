# Quick run

## Installation

Either install warnet via pip, or clone the source and install:

### via pip

You can install warnet via `pip` into a virtual environment with

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install warnet
```

### via cloned source

You can install warnet from source into a virtual environment with

```bash
git clone https://github.com/bitcoin-dev-project/warnet.git
cd warnet
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Running

To get started first check you have all the necessary requirements:

```bash
warnet setup
```

Then create your first network:

```bash
# Create a new network in the current directory
warnet init

# Or in a directory of choice
warnet new <directory>
```

Follow the guide to configure network variables.

## fork-observer

If you enabled [fork-observer](https://github.com/0xB10C/fork-observer), it will be available from the landing page at `localhost:2019`.
