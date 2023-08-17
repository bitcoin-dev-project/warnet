export type GraphNode = {
  id: number;
  size: number;
  x: number;
  y: number;
};

export type GraphEdge = {
  id: number;
  source: Source;
  target: Source;
  value: number;
};

export type Source = {
  id: string;
  label: string;
  x: number;
  y: number;
  fx: number;
  fy: number;
  size: number;
  vx: number;
  vy: number;
};

export type GraphData = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};
