import { GraphEdge, GraphNode, NodePersona, SavedNetworkGraph } from "@/flowTypes";
import { Edge, Node } from "reactflow";

export const defaultEdgesData: Edge<GraphEdge>[] = [
  {
    id: "e0-1",
    source: "0",
    target: "1",
  },
  {
    id: "e0-2",
    source: "0",
    target: "2",
  },
  {
    id: "e1-3",
    source: "1",
    target: "3",
  },
  {
    id: "e0-3",
    source: "0",
    target: "3",
  },
  {
    id: "e0-6",
    source: "0",
    target: "6",
  },
  {
    id: "e6-3",
    source: "6",
    target: "3",
  },
  {
    id: "e4-6",
    source: "4",
    target: "6",
  },
  {
    id: "e1-5",
    source: "1",
    target: "6",
  },
];

export const defaultNodesData: Node<GraphNode>[] = [
  {
    id: "0",
    type:"draggable",
    data: {
    id: "0",
    label: "node 0",
    version: "20.0",
    latency: "10ms",
    size: 10,
    baseFee: 0.5,
    },
    position:{
      x:100,
      y:100,
    }
  },
  {
    id: "1",
    type:"draggable",
    data:{
    id: "1",
    label: "node 1",
    version: "22.1",
    latency: "20ms",
    size: 10,
    baseFee: 0.4,
    },
    position:{
      x:100,
      y:200,
    }
  },
  {
    id: "2",
    type:"draggable",
    data:{
    id: "2",
    label: "miner node 2",
    version: "21.0",
    latency: "5ms",
    size: 10,
    baseFee: 0.3,
    },
    position:{
      x:100,
      y:300,
    }
  },
  {
    id: "3",
    type:"draggable",
    data:{
    id: "3",
    label: "node 3",
    version: "20.0",
    latency: "15ms",
    size: 10,
    baseFee: 0.2,
    },
    position:{
      x:100,
      y:400,
    }
  },
  {
    id: '4',
    type:"draggable",
    data:{
    id: "4",
    label: "node 4",
    version: "22.1",
    latency: "20ms",
    size: 10,
    baseFee: 0.4,
    },
    position:{
      x:100,
      y:500,
    }
  },
  {
    id: "5",
    type:"draggable",
    data:{
    id: "5",
    label: "miner node 5",
    version: "21.0",
    latency: "5ms",
    size: 10,
    baseFee: 0.3,
    },
    position:{
      x:100,
      y:500,
    }
  },
  {
    id: "6",
    type:"draggable",
    data:{
    id: "6",
    label: "node 6",
    version: "20.0",
    latency: "15ms",
    size: 10,
    baseFee: 0.2,
    },
    position:{
      x:100,
      y:500,
    }
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
    },
  },
];
