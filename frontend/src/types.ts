import * as NetworkContextExports from "./contexts/network-context";

export type GraphNode = {
  id?: number;
  size: number;
  name?: string;
  version?: string;
  latency?: string;
  baseFee?: number;
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
  edges: GraphEdge[];
  nodes: GraphNode[];
};

export type NetworkPersona = {
  type: NodePersonaType
  persona: NodePersona
}

export type NodeGraphContext = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  isDialogOpen: boolean;
  openDialog: () => void;
  closeDialog: () => void;
  nodePersonaType: NodePersonaType | null;
  addNode: (node?: GraphNode[]) => void;
  setNodePersonaFunc: ({type, nodePersona}: NetworkTopology) => void;
  setNodeEdges: (
    edge: GraphEdge[],
    selectedNode?: GraphNode,
    d?: GraphNode
  ) => void;
  showGraph: boolean;
  showGraphFunc: () => void;
  showNodePersonaInfo: () => void;
  nodePersona: NodePersona | null;
  generateNodeGraph: () => void;
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
