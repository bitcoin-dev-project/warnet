import typer
import logging
import docker
from datetime import datetime
import warnet
from warnet import get_bitcoin_cli, get_bitcoin_debug_log, get_messages, stop_network, wipe_network

BITCOIN_GRAPH_FILE = './graphs/basic3.graphml'

logging.basicConfig(level=logging.INFO)
warnet_app = typer.Typer()
run_app = typer.Typer()
warnet_app.add_typer(run_app, name="run", help="Run a warnet. `warnet run --help` for more info")


@warnet_app.command()
def bcli(node: int, method: str, params: list[str] = typer.Option([]), network: str = "warnet"):
    """
    Call bitcoin-cli <method> <params> on <node> in [network]
    """
    print(f"{node}")
    print(f"{method}")
    print(f"{params}")
    try:
        result = get_bitcoin_cli(node, method, params, network)
        typer.echo(result)
    except Exception as e:
        typer.echo(f"In our quest to command node {node}, we encountered resistance: {e}")


@warnet_app.command()
def debug_log(node: int, network: str = "warnet"):
    """
    Fetch the Bitcoin Core debug log from <node>
    """
    try:
        result = get_bitcoin_debug_log(node, network)
        typer.echo(result)
    except Exception as e:
        typer.echo(f"In our pursuit of knowledge from node {node}, we were thwarted: {e}")

@warnet_app.command()
def messages(node_a: int, node_b: int):
    """
    Fetch messages sent between <node_a> and <node_b>.
    """
    try:
        messages = get_messages(node_a, node_b)
        out = ""
        for m in messages:
            timestamp = datetime.utcfromtimestamp(m["time"] / 1e6).strftime('%Y-%m-%d %H:%M:%S')
            direction = ">>>" if m["outbound"] else "<<<"
            body = ""
            if "body" in m:
                body = m["body"]
            out = out + f"{timestamp} {direction} {m['msgtype']} {body}\n"
        typer.echo(out)
    except Exception as e:
        typer.echo(f"Amidst the fog of war, we failed to relay messages between strongholds {node_a} and {node_b}: {e}")


@run_app.command()
def from_file(graph_file: str = BITCOIN_GRAPH_FILE):
    """
    Run warnet from a graph file. Options: --graph-file TEXT    Path to the graph file (default: ./graphs/basic3.graphml)
    """
    client = docker.from_env()
    warnet.generate_docker_compose(graph_file)
    warnet.docker_compose()
    warnet.apply_network_conditions(client, graph_file)
    warnet.connect_edges(client, graph_file)


@warnet_app.command()
def stop(network: str = "warnet"):
    """
    Stop all docker containers in <network>.
    """
    try:
        result = stop_network(network)
        typer.echo(result)
    except Exception as e:
        typer.echo(f"As we endeavored to cease operations, adversity struck: {e}")

@warnet_app.command()
def wipe(network: str = "warnet"):
    """
    Stop and then erase all docker containers in <network>, and then the docker network itself.
    """
    try:
        result = stop_network(network)
        typer.echo(result)
    except Exception as e:
        typer.echo(f"Error stopping containers: {e}")
    try:
        result = wipe_network(network)
        typer.echo(result)
    except Exception as e:
        typer.echo(f"Error wiping network: {e}")


if __name__ == "__main__":
    warnet_app()
