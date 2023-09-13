import { GraphEdge, GraphNode } from "@/flowTypes";
import { Edge, Node } from "reactflow";

const getNodePeers = (
  nodeId: number | string,
  nodes: Node<GraphNode>[],
  edges: Edge<GraphEdge>[]
) => {
  const nodeEdges = edges.filter(
    (edge) => edge.source === nodeId || edge.target === nodeId
  );
  const nodePeers = nodeEdges.map((edge) => {
    return nodes.find((node) => node.id === edge.target);
  });
  return nodePeers;
};

export default getNodePeers;
