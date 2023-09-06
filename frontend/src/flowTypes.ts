import { Edge, EdgeChange, Node, NodeChange, OnEdgesChange, OnNodesChange } from "reactflow";
import { BITCOIN_CORE_BINARY_VERSIONS, CPU_CORES, NODE_LATENCY, RAM_OPTIONS } from "./config";
import * as NetworkContextExports from "./contexts/network-context";
import { Dispatch } from "react";

export type GraphNode = {
  id?: number;
  size: number;
  label?: string;
  name?: string;
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
  edges: Edge<Partial<GraphEdge>>[];
  nodes: Node<Partial<GraphNode>>[];
};

export type NetworkPersona = {
  type: NodePersonaType
  persona: NodePersona
}

export type NodeGraphContext = {
  nodes: Node<Partial<GraphNode>>[];
  edges: Edge<Partial<GraphEdge>>[];
  isDialogOpen: boolean;
  openDialog: () => void;
  closeDialog: () => void;
  nodePersonaType: NodePersonaType | null;
  setNodes: Dispatch<React.SetStateAction<Node<any, string | undefined>[]>>;
  setEdges: Dispatch<React.SetStateAction<Edge<any>[]>>;
  addNode: (node?:Node<Partial<GraphNode>>) => void;
  duplicateNode: (node: Node<Partial<GraphNode>>) => void;
  setNodePersonaFunc: ({type, nodePersona}: NetworkTopology) => void;
  setNodeEdges: (
    edge: Edge<Partial<GraphEdge>>[],
    selectedNode?: Node<Partial<GraphNode>>,
    d?:Node<Partial<GraphNode>>
  ) => void;
  showGraph: boolean;
  showGraphFunc: () => void;
  showNodePersonaInfo: () => void;
  nodePersona: NodePersona | null;
  generateNodeGraph: () => void;
  nodeInfo: Node<Partial<GraphNode>> | null;
  editNode: (node: Node<Partial<GraphNode>>) => void;
  deleteNode: (node: Node<Partial<GraphNode>>) => void;
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
