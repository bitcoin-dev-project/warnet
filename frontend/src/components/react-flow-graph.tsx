"use client";

import React, { useRef, useEffect, useLayoutEffect, useCallback } from "react";
import Sidebar from "./sidebar";
import NodeInfo from "./node-info-dialog";
import ReactFlow, { Node, addEdge }  from "reactflow";
import { useNodeFlowContext } from "@/contexts/node-flow-context";

const ReactFlowGraph = () => {
    const { nodes, edges, isDialogOpen, showGraph, setEdges, onNodesChange, onEdgesChange } =
    useNodeFlowContext();
    const onConnect = useCallback((params:any) => setEdges((eds) => addEdge(params, eds)), []);
  if (!showGraph) {
    return null;
  }
  return (
    <>
      <Sidebar />
      {isDialogOpen && <NodeInfo />}
      <div id="canvas" className="w-full h-full bg-brand-gray-medium border border-black">
        <ReactFlow nodes={nodes || []} edges={edges || []} onConnect={onConnect} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} />
    </div>
    </>
  );
};

export default ReactFlowGraph;
