import json
from io import BytesIO
from pathlib import Path

import click
import networkx as nx
from rich import print
from warnet.utils import DEFAULT_TAG, create_cycle_graph, validate_graph_schema


@click.group(name="graph")
def graph():
    """Create and validate network graphs"""


@graph.command()
@click.argument("number", type=int)
@click.option("--outfile", type=click.Path())
@click.option("--version", type=str, default=DEFAULT_TAG)
@click.option("--bitcoin_conf", type=click.Path())
@click.option("--random", is_flag=True)
def create(number: int, outfile: Path, version: str, bitcoin_conf: Path, random: bool = False):
    """
    Create a cycle graph with <number> nodes, and include 7 extra random outbounds per node.
    Returns XML file as string with or without --outfile option
    """
    graph = create_cycle_graph(number, version, bitcoin_conf, random)

    if outfile:
        file_path = Path(outfile)
        nx.write_graphml(graph, file_path, named_key_ids=True)
    bio = BytesIO()
    nx.write_graphml(graph, bio, named_key_ids=True)
    xml_data = bio.getvalue()
    print(xml_data.decode("utf-8"))


@graph.command()
@click.argument("infile", type=click.Path())
@click.option("--outfile", type=click.Path())
@click.option("--cb", type=str)
@click.option("--ln_image", type=str)
def import_json(infile: Path, outfile: Path, cb: str, ln_image: str):
    """
    Create a cycle graph with nodes imported from lnd `describegraph` JSON file,
    and additionally include 7 extra random outbounds per node. Include lightning
    channels and their policies as well.
    Returns XML file as string with or without --outfile option.
    """
    with open(infile) as f:
        json_graph = json.loads(f.read())

    # Start with a connected L1 graph with the right amount of tanks
    graph = create_cycle_graph(
        len(json_graph["nodes"]), version=DEFAULT_TAG, bitcoin_conf=None, random_version=False
    )

    # Initialize all the tanks with basic LN node configurations
    for index, n in enumerate(graph.nodes()):
        graph.nodes[n]["bitcoin_config"] = f"-uacomment=tank{index:06}"
        graph.nodes[n]["ln"] = "lnd"
        graph.nodes[n]["ln_config"] = "--protocol.wumbo-channels"
        if cb:
            graph.nodes[n]["ln_cb_image"] = cb
        if ln_image:
            graph.nodes[n]["ln_image"] = ln_image

    # Save a map of LN pubkey -> Tank index
    ln_ids = {}
    for index, node in enumerate(json_graph["nodes"]):
        ln_ids[node["pub_key"]] = index

    # Offset for edge IDs
    # Note create_cycle_graph() creates L1 edges all with the same id "0"
    L1_edges = len(graph.edges)

    # Insert LN channels
    # Ensure channels are in order by channel ID like lnd describegraph output
    sorted_edges = sorted(json_graph["edges"], key=lambda chan: int(chan["channel_id"]))
    for ln_index, channel in enumerate(sorted_edges):
        src = ln_ids[channel["node1_pub"]]
        tgt = ln_ids[channel["node2_pub"]]
        cap = int(channel["capacity"])
        push = cap // 2
        openp = f"--local_amt={cap} --push_amt={push}"
        srcp = ""
        tgtp = ""
        if channel["node1_policy"]:
            srcp += f" --base_fee_msat={channel['node1_policy']['fee_base_msat']}"
            srcp += f" --fee_rate_ppm={channel['node1_policy']['fee_rate_milli_msat']}"
            srcp += f" --time_lock_delta={max(int(channel['node1_policy']['time_lock_delta']), 18)}"
            srcp += f" --min_htlc_msat={max(int(channel['node1_policy']['min_htlc']), 1)}"
            srcp += f" --max_htlc_msat={push * 1000}"
        if channel["node2_policy"]:
            tgtp += f" --base_fee_msat={channel['node2_policy']['fee_base_msat']}"
            tgtp += f" --fee_rate_ppm={channel['node2_policy']['fee_rate_milli_msat']}"
            tgtp += f" --time_lock_delta={max(int(channel['node2_policy']['time_lock_delta']), 18)}"
            tgtp += f" --min_htlc_msat={max(int(channel['node2_policy']['min_htlc']), 1)}"
            tgtp += f" --max_htlc_msat={push * 1000}"

        graph.add_edge(
            src,
            tgt,
            key=ln_index + L1_edges,
            channel_open=openp,
            source_policy=srcp,
            target_policy=tgtp,
        )

    if outfile:
        file_path = Path(outfile)
        nx.write_graphml(graph, file_path, named_key_ids=True)
    bio = BytesIO()
    nx.write_graphml(graph, bio, named_key_ids=True)
    xml_data = bio.getvalue()
    print(xml_data.decode("utf-8"))


@graph.command()
@click.argument("graph", type=click.Path())
def validate(graph: Path):
    """
    Validate a <graph file> against the schema.
    """
    with open(graph) as f:
        graph = nx.parse_graphml(f.read(), node_type=int, force_multigraph=True)
    return validate_graph_schema(graph)
