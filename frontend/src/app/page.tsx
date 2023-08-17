"use client";

import React, { useState } from "react";

import ForceGraph from "@/components/force-graph";
import Sidebar from "@/components/sidebar";
import { CANVAS_HEIGHT, CANVAS_WIDTH } from "@/config";
import { GraphNode } from "@/types";

export default function Home() {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [links, setLinks] = useState([]);

  React.useEffect(() => {
    console.log("links", links);
  }, [links]);

  const addNode = () => {
    const newNode = {
      id: nodes.length,
      size: 10,
      x: CANVAS_WIDTH / 2,
      y: CANVAS_HEIGHT / 2,
    };
    setNodes([...nodes, newNode]);
  };

  const handleNodeDrag = (node: GraphNode) => {
    setNodes((prevNodes) =>
      prevNodes.map((n) => (n.id === node.id ? node : n))
    );
  };
  return (
    <main className="bg-white flex min-h-screen items-center justify-between">
      <Sidebar onAddNode={addNode} />
      <section className="flex flex-col items-center justify-center w-5/6 min-h-screen bg-white">
        <ForceGraph nodes={nodes} edges={links} setLinks={setLinks} />
      </section>
    </main>
  );
}
