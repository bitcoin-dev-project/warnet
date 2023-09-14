import {
  GraphEdge,
  GraphNode,
  NodePersona,
  SavedNetworkGraph,
} from "@/flowTypes";
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
    type: "draggable",
    data: {
      id: "0",
      label: "node 0",
      version: "25.0",
      latency: "10ms",
      size: 10,
      baseFee: 0.5,
    },
    position: {
      x: 100,
      y: 100,
    },
  },
  {
    id: "1",
    type: "draggable",
    data: {
      id: "1",
      label: "node 1",
      version: "24.0.1",
      latency: "20ms",
      size: 10,
      baseFee: 0.4,
    },
    position: {
      x: 100,
      y: 200,
    },
  },
  {
    id: "2",
    type: "draggable",
    data: {
      id: "2",
      label: "miner node 2",
      version: "23.0",
      latency: "5ms",
      size: 10,
      baseFee: 0.3,
    },
    position: {
      x: 100,
      y: 300,
    },
  },
  {
    id: "3",
    type: "draggable",
    data: {
      id: "3",
      label: "node 3",
      version: "22.0",
      latency: "15ms",
      size: 10,
      baseFee: 0.2,
    },
    position: {
      x: 100,
      y: 400,
    },
  },
  {
    id: "4",
    type: "draggable",
    data: {
      id: "4",
      label: "node 4",
      version: "0.21.1",
      latency: "20ms",
      size: 10,
      baseFee: 0.4,
    },
    position: {
      x: 100,
      y: 500,
    },
  },
  {
    id: "5",
    type: "draggable",
    data: {
      id: "5",
      label: "miner node 5",
      version: "0.20.1",
      latency: "5ms",
      size: 10,
      baseFee: 0.3,
    },
    position: {
      x: 100,
      y: 500,
    },
  },
  {
    id: "6",
    type: "draggable",
    data: {
      id: "6",
      label: "node 6",
      version: "0.21.0",
      latency: "15ms",
      size: 10,
      baseFee: 0.2,
    },
    position: {
      x: 100,
      y: 500,
    },
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

// export const newNetwork: NodePersona = {
//   id: 0,
//   name: "Alice",
//   version: "22.0",
//   latency: "10ms",
//   peers: 8,
//   baseFee: 0.5,
//   edges: [],
//   nodes: [{
//     id: "0",
//     type:"draggable",
//     data: {
//     id: "0",
//     label: "node 0",
//     version: "25.0",
//     latency: "0ms",
//     size: 10,
//     baseFee: 0.5,
//     },
//     position:{
//       x:100,
//       y:100,
//     }
//   }],
// }

export const tempSavednetwork: SavedNetworkGraph[] = [
  {
    type: "custom",
    nodePersona: {
      id: 4,
      name: "Mini bitcoin network",
      version: "22.0",
      latency: "10ms",
      peers: 8,
      baseFee: 0.5,
      edges: defaultEdgesData,
      nodes: defaultNodesData,
    },
  },
  {
    type: "prebuilt",
    graphmlPath: "barabasi_albert_graph_n100_m3_pos.graphml",
    nodePersona: {
      id: 0,
      name: "barabasi_albert_graph",
      version: "22.0",
      latency: "10ms",
      peers: 100,
      baseFee: 0.5,
      edges: [],
      nodes: [],
    },
  },
  {
    type: "prebuilt",
    graphmlPath: "navigable_small_world_graph_n10_p1_q3_r2_dim2_pos.graphml",
    nodePersona: {
      id: 1,
      name: "navigable_small_world",
      version: "22.0",
      latency: "10ms",
      peers: 100,
      baseFee: 0.5,
      edges: [],
      nodes: [],
    },
  },
  {
    type: "prebuilt",
    graphmlPath: "random_geometric-graph_n100_r0.2.graphml",
    nodePersona: {
      id: 2,
      name: "random_geometric_graph",
      version: "22.0",
      latency: "10ms",
      peers: 100,
      baseFee: 0.5,
      edges: [],
      nodes: [],
    },
  },
  {
    type: "prebuilt",
    graphmlPath: "wheel_graph_n100_pos.graphml",
    nodePersona: {
      id: 3,
      name: "wheel_graph",
      version: "22.0",
      latency: "10ms",
      peers: 100,
      baseFee: 0.5,
      edges: [],
      nodes: [],
    },
  },
];
