import { GraphEdge, GraphNode } from "@/types";
import { parse } from "js2xmlparser";

type GraphElement = {
  nodes: GraphNode[];
  edges: GraphEdge[];
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
          id: "edgelabel",
          for: "edge",
          attr_name: "Edge Label",
          attr_type: "string",
        },
      },
      {
        "@": {
          id: "weight",
          for: "edge",
          attr_name: "weight",
          attr_type: "double",
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
            { "@": { key: "label" }, "#": node.name },
            { "@": { key: "size" }, "#": node.size },
            { "@": { key: "version" }, "#": node.version },
            { "@": { key: "latency" }, "#": node.latency },
            { "@": { key: "baseFee" }, "#": node.baseFee },
            { "@": { key: "x" }, "#": node.x },
            { "@": { key: "y" }, "#": node.y },
          ],
        })),
        edge: edges.map((edge) => ({
          "@": {
            id: edge.source.id,
            source: edge.source.id,
            target: edge.target.id,
          },
          data: [
            { "@": { key: "edgelabel" }, "#": edge.source.name },
            { "@": { key: "weight" }, "#": edge.source.size },
          ],
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
