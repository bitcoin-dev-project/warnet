import { GraphEdge, GraphNode, NodePersona, SavedNetworkGraph } from "@/types";

export const defaultEdgesData: GraphEdge[] = [
  {
    source: 0,
    target: 1,
  },
  {
    source: 0,
    target: 2,
  },
  {
    source: 1,
    target: 3,
  },
  {
    source: 0,
    target: 3,
  },
  {
    source: 0,
    target: 6,
  },
  {
    source: 6,
    target: 3,
  },
  {
    source: 4,
    target: 6,
  },
  {
    source: 1,
    target: 5,
  },
];

export const defaultNodesData: GraphNode[] = [
  {
    id: 0,
    name: "node 0",
    version: "20.0",
    latency: "10ms",
    size: 10,
    baseFee: 0.5,
  },
  {
    id: 1,
    name: "node 1",
    version: "22.1",
    latency: "20ms",
    size: 10,
    baseFee: 0.4,
  },
  {
    id: 2,
    name: "miner node 2",
    version: "21.0",
    latency: "5ms",
    size: 10,
    baseFee: 0.3,
  },
  {
    id: 3,
    name: "node 3",
    version: "20.0",
    latency: "15ms",
    size: 10,
    baseFee: 0.2,
  },
  {
    id: 4,
    name: "node 4",
    version: "22.1",
    latency: "20ms",
    size: 10,
    baseFee: 0.4,
  },
  {
    id: 5,
    name: "miner node 5",
    version: "21.0",
    latency: "5ms",
    size: 10,
    baseFee: 0.3,
  },
  {
    id: 6,
    name: "node 6",
    version: "20.0",
    latency: "15ms",
    size: 10,
    baseFee: 0.2,
  },
];

export const defaultNodePersona: NodePersona = {
  id: 0,
  name: "Alice",
  version: "22.0",
  latency: "10ms",
  peers: 8,
  baseFee: 0.5,
  edges: defaultEdgesData,
  nodes: defaultNodesData,
};

export const tempSavednetwork: SavedNetworkGraph[] = [
  {
    date: new Date(),
    type: "prebuilt",
    nodePersona: {
      id: 0,
      name: "Alice",
      version: "22.0",
      latency: "10ms",
      peers: 8,
      baseFee: 0.5,
      edges: defaultEdgesData,
      nodes: defaultNodesData,
    } 
  }
]
