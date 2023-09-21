import { GraphEdge, GraphNode } from "@/flowTypes";
import { parse } from "js2xmlparser";
import type { Edge, Node } from "reactflow";

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
          ["attr.name"]: "label",
          ["attr.type"]: "string",
        },
      },
      {
        "@": {
          id: "size",
          for: "node",
          ["attr.name"]: "size",
          ["attr.type"]: "double",
        },
      },
      {
        "@": {
          id: "version",
          for: "node",
          ["attr.name"]: "version",
          ["attr.type"]: "string",
        },
      },
      {
        "@": {
          id: "latency",
          for: "node",
          ["attr.name"]: "latency",
          ["attr.type"]: "string",
        },
      },
      {
        "@": {
          id: "bitcoin_conf",
          for: "node",
          ["attr.name"]: "bitcoin_conf",
          ["attr.type"]: "string",
        },
      },
      {
        "@": {
          id: "x",
          for: "node",
          ["attr.name"]: "x",
          ["attr.type"]: "float",
        },
      },
      {
        "@": {
          id: "y",
          for: "node",
          ["attr.name"]: "y",
          ["attr.type"]: "float",
        },
      },
      {
        "@": {
          id: "tc_netem",
          for: "node",
          ["attr.name"]: "tc_netem",
          ["attr.type"]: "float",
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
              // { "@": { key: "baseFee" }, "#": node.data.baseFee || "" },
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
  const a = document.createElement("a");
  a.href = url;
  a.download = "graph.graphml";
  a.click();
};

export default generateGraphML;
