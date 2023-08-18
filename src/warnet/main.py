import typer
import sys
import pkgutil
import os
import subprocess
from datetime import datetime
import logging
import docker
import warnet
from warnet.connect_nodes import *
from warnet.client import *

app = typer.Typer()

@app.command()
def bcli(node: int, method: str, params: list[str] = typer.Option([])):
    """
    On the battlefield of node {node}, we dispatch the command '{method}' with the marching orders '{params}'.
    """
    try:
        result = get_bitcoin_cli(node, method, params)
        typer.echo(result)
    except Exception as e:
        typer.echo(f"In our quest to command node {node}, we encountered resistance: {e}")

@app.command()
def log(node: int):
    """
    From the archives of node {node}, we shall unveil the tales and chronicles of its endeavors.
    """
    try:
        result = get_debug_log(node)
        typer.echo(result)
    except Exception as e:
        typer.echo(f"In our pursuit of knowledge from node {node}, we were thwarted: {e}")

@app.command()
def messages(src: int, dst: int):
    """
    Relaying the dispatches exchanged between the strongholds of nodes {src} and {dst}.
    """
    try:
        messages = get_messages(src, dst)
        out = ""
        for m in messages:
            timestamp = datetime.utcfromtimestamp(m["time"] / 1e6).strftime('%Y-%m-%d %H:%M:%S')
            direction = "Advance" if m["outbound"] else "Retreat"
            body = m.get("body", "")
            out += f"At the hour of {timestamp}, the order was to '{direction}' bearing the message '{m['msgtype']} {body}'\n"
        typer.echo(out)
    except Exception as e:
        typer.echo(f"Amidst the fog of war, we failed to relay messages between strongholds {src} and {dst}: {e}")

@app.command()
def run(scenario_name: str, args: list[str] = typer.Option([])):
    """
    With valor and courage, we embark on the mission named '{scenario_name.py}', armed with the strategies '{args}'.
    """
    dir_path = os.path.dirname(os.path.realpath(__file__))
    mod_path = os.path.join(dir_path, '..', 'scenarios', f"{scenario_name}.py")
    run_cmd = [sys.executable, mod_path] + args
    subprocess.run(run_cmd)

@app.command()
def stop():
    """
    In the face of overwhelming odds, we make the strategic decision to halt our operations and regroup.
    """
    try:
        result = stop_network()
        typer.echo(result)
    except Exception as e:
        typer.echo(f"As we endeavored to cease operations, adversity struck: {e}")

@app.command()
def generate(nodes: int, probability: float):
    """
    With valor and foresight, we shall forge a battlefield of {nodes} strongholds, where alliances are formed with a probability of {probability}.
    """
    try:
        client = docker.from_env()
        warnet.delete_containers(client)
        graph = create_graph_with_probability(nodes, probability)
        warnet.generate_docker_compose(graph)
        warnet.docker_compose()
        generate_topology(client, graph)
        typer.echo(f"A grand theater of war with {nodes} strongholds has been crafted, with alliances formed at the whims of chance, set at a probability of {probability}.")
    except Exception as e:
        typer.echo(f"While crafting our theater of war with {nodes} strongholds, we faced an unexpected challenge: {e}")

@app.command()
def load(file: str):
    """
    With the map of {file} in hand, we shall lay out our strategy and position our forces accordingly.
    """
    try:
        client = docker.from_env()
        warnet.delete_containers(client)
        warnet.generate_docker_compose(file)
        warnet.docker_compose()
        generate_topology_from_file(client, file)
        typer.echo(f"The battle plans from {file} have been unfurled and our strategy is clear.")
    except Exception as e:
        typer.echo(f"In our endeavor to decipher the plans from {file}, we encountered a setback: {e}")


if __name__ == "__main__":
    app()
