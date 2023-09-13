import { Edge, EdgeChange, Node, NodeChange, OnEdgesChange, OnNodesChange } from "reactflow";
import { BITCOIN_CORE_BINARY_VERSIONS, CPU_CORES, NODE_LATENCY, RAM_OPTIONS } from "./config";
import * as NetworkContextExports from "./contexts/network-context";
import { Dispatch } from "react";

export type GraphNode = {
  id: string;
  size: number;
  label?: string;
  version?: typeof BITCOIN_CORE_BINARY_VERSIONS[number];
  latency?: typeof NODE_LATENCY[number];
  baseFee?: number;
  ram?: typeof RAM_OPTIONS[number]
  cpu?: typeof CPU_CORES[number]
  x?: number;
  y?: number;
};

export type GraphEdge = {
  id?: number;
  source: any;
  target: any;
  value?: number;
};

export type GraphData = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};
export type NodePersonaType = "custom" | "prebuilt";

export type NodePersona = {
  id: number;
  name: string;
  version: string;
  latency: string;
  peers: number;
  baseFee: number;
  edges: Edge<GraphEdge>[];
  nodes: Node<GraphNode>[];
};

export type NetworkPersona = {
  type: NodePersonaType
  persona: NodePersona
}

export type NodeGraphContext = {
  nodes: Node<GraphNode>[];
  edges: Edge<GraphEdge>[];
  isDialogOpen: boolean;
  openDialog: () => void;
  closeDialog: () => void;
  nodePersonaType: NodePersonaType | null;
  setNodes: Dispatch<React.SetStateAction<Node<GraphNode>[]>>;
  setEdges: Dispatch<React.SetStateAction<Edge<GraphEdge>[]>>;
  addNode: (node?:Node<GraphNode>) => void;
  duplicateNode: (node: Node<GraphNode>) => void;
  setNodePersonaFunc: ({type, nodePersona}: NetworkTopology) => void;
  setNodeEdges: (
    edge: Edge<GraphEdge>[],
    selectedNode?: Node<GraphNode>,
    d?:Node<GraphNode>
  ) => void;
  showGraph: boolean;
  showGraphFunc: () => void;
  showNodePersonaInfo: () => void;
  nodePersona: NodePersona | null;
  generateNodeGraph: () => void;
  nodeInfo: Node<GraphNode> | null;
  editNode: (node: Node<GraphNode>) => void;
  selectNode: (id: Node["id"]) => void;
  deleteNode: (node: Node<GraphNode>) => void;
  updateNodeInfo: (nodeProperty: any, value: any) => void;
  saveEditedNode: () => void;
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
};

export type NetworkContext = {
  steps: NetworkContextExports.Steps;
  selectedNetwork: NetworkTopology;
  setSelectedNetwork: (value: NetworkTopology) => void;
  isDialogOpen: boolean;
  networkList: SavedNetworkGraph[];
  networkTopologyList: NetworkTopology[];
  setNetworkList: (list: SavedNetworkGraph[]) => void;
  // uploadToNodeGraph: () => void;
  openDialog: () => void;
  closeDialog: () => void;
  setStep: (step: NetworkContextExports.Steps) => void;
}

export type SavedNetworkGraph = {
  type: NodePersonaType;
  nodePersona: NodePersona;
  date: Date;
}
export type NetworkTopology = Omit<SavedNetworkGraph, "date">
