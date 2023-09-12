import { GraphEdge, GraphNode } from "@/flowTypes";
import { parse } from "js2xmlparser";
import { Edge, Node } from "reactflow";

type GraphElement = {
  nodes: Node<GraphNode>[];
  edges: Edge<GraphEdge>[];
};

const generateGraphML = ({ nodes, edges }: GraphElement) => {
  const graphmlData = {
    key: [
      {
        "@": {
          id: "label",
          for: "node",
          attr_name: "label",
          attr_type: "string",
        },
      },
      {
        "@": {
          id: "size",
          for: "node",
          attr_name: "size",
          attr_type: "double",
        },
      },
      {
        "@": {
          id: "version",
          for: "node",
          attr_name: "version",
          attr_type: "string",
        },
      },
    ],
    graph: {
      "@": {
        edgedefault: "directed",
      },
      "#": {
        node: nodes.map((node) => ({
          "@": {
            id: node.id,
          },
          data: [
            { "@": { key: "label" }, "#": node.data.label },
            { "@": { key: "size" }, "#": node.data.size },
            { "@": { key: "version" }, "#": node.data.version },
            { "@": { key: "latency" }, "#": node.data.latency },
            { "@": { key: "baseFee" }, "#": node.data.baseFee },
            { "@": { key: "x" }, "#": node.position.x },
            { "@": { key: "y" }, "#": node.position.y },
          ],
        })),
        edge: edges.map((edge) => ({
          "@": {
            id: edge.source,
            source: edge.source,
            target: edge.target,
          },
        })),
      },
    },
  };

  const xml = parse("graphml", graphmlData);
  const blob = new Blob([xml], { type: "application/xml" });
  const url = URL.createObjectURL(blob);
  console.log({ xml });
  const a = document.createElement("a");
  a.href = url;
  a.download = "graph.graphml";
  a.click();
};

export default generateGraphML;
