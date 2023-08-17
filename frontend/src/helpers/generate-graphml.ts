import { GraphEdge, GraphNode } from "@/types";
import { parse } from "js2xmlparser";

type GraphElement = {
  nodes: GraphNode[];
  links: GraphEdge[];
};

const downloadGraphML = ({ nodes, links }: GraphElement) => {
  const graphmlData = {
    "@": {
      xmlns: "http://graphml.graphdrawing.org/xmlns",
      edgedefault: "directed",
    },
    key: [
      // Define the attributes you need
    ],
    graph: {
      node: nodes,
      edge: links,
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

export default downloadGraphML;
