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
        node: nodes.map((node) => {
          const nodesBitcoinConf =
            Object.entries(node.data?.bitcoin_conf || {}).flat() || [];
          let result = "";
          for (let i = 2; i < nodesBitcoinConf.length; i += 2) {
            result += `${nodesBitcoinConf[i]}=${nodesBitcoinConf[i + 1]},`;
          }
          return {
            "@": {
              id: node.id,
            },
            data: [
              { "@": { key: "label" }, "#": node.data.label },
              { "@": { key: "version" }, "#": node.data.version || "" },
              { "@": { key: "latency" }, "#": node.data.latency || "" },
              { "@": { key: "baseFee" }, "#": node.data.baseFee || "" },
              { "@": { key: "x" }, "#": node.position.x },
              { "@": { key: "y" }, "#": node.position.y },
              { "@": { key: "bitcoin_conf" }, "#": result },
            ],
          };
        }),
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
  const downloadLink = document.createElement("a");
  downloadLink.href = url;
  downloadLink.download = "graph.graphml";
  downloadLink.click();
};

export default generateGraphML;
