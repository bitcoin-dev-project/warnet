import { GraphEdge, GraphNode } from "@/types";

const getNodePeers = (
  nodeId: number,
  nodes: GraphNode[],
  edges: GraphEdge[]
) => {
  const nodeEdges = edges.filter(
    (edge) => edge.source.id === nodeId || edge.target.id === nodeId
  );
  const nodePeers = nodeEdges.map((edge) => {
    return nodes.find((node) => node.id === edge.target);
  });
  return nodePeers;
};

export default getNodePeers;
