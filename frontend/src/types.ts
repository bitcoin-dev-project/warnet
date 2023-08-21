import { Steps } from "./contexts/node-graph-context";

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

export type NodeGraphContext = {
  steps: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  isDialogOpen: boolean;
  openDialog: () => void;
  closeDialog: () => void;
  nodePersonaType: NodePersonaType | null;
  addNode: (node?: GraphNode[]) => void;
  setNodePersonaFunc: (persona: NodePersonaType) => void;
  setNodeEdges: (
    edge: GraphEdge[],
    selectedNode?: GraphNode,
    d?: GraphNode
  ) => void;
  showGraph: boolean;
  setStep: (step: Steps) => void;
  showGraphFunc: () => void;
  showNodePersonaInfo: () => void;
  nodePersona: NodePersona | null;
  generateNodeGraph: () => void;
};
