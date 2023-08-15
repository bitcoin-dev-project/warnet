# Warnet

Make sure to have docker and docker-compose installed

1. Install the dependencies:

It is recommended to create a virtual environment, like so:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

and then install the dependencies from the requirements.txt file:

```bash
pip install -r requirements.txt
```

2. start the docker containers. (Each container is a node as described in the graph)

```bash
python connect_nodes.py
```
