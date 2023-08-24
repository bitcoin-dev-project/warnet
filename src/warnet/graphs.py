import networkx as nx


def read_graph_file(file: str) -> nx.Graph:
    graph = nx.read_graphml(file, node_type=int)
    return graph

