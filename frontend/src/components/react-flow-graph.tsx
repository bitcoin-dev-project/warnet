"use client";

import React, { useCallback, useMemo } from "react";
import Sidebar from "./sidebar";
import NodeInfo from "./node-info-dialog";
import ReactFlow, { addEdge, Background, BackgroundVariant, NodeDragHandler, OnMove } from "reactflow";
import { useNodeFlowContext } from "@/contexts/node-flow-context";
import DraggableNode from "./DraggableNode";

const ReactFlowGraph = () => {
  const {
    nodes,
    edges,
    nodeInfo,
    selectNode,
    isDialogOpen,
    showGraph,
    setEdges,
    onNodesChange,
    onEdgesChange,
  } = useNodeFlowContext();
  const onConnect = useCallback(
    (params: any) => setEdges((eds) => addEdge(params, eds)),
    []
  );
  const nodeTypes = useMemo(() => ({ draggable: DraggableNode }), []);
  if (!showGraph) {
    return null;
  }
  const handleNodeDrag: NodeDragHandler = (e) => {
    const { id } = e.target as HTMLElement
    if (!id || nodeInfo?.id === id) return
    selectNode(id)
  }
  const handlePaneClick = (e: React.MouseEvent<Element, MouseEvent>) => {
    selectNode(null)
  }
  return (
    <>
      <Sidebar />
      {isDialogOpen && <NodeInfo />}
      <div
        id="canvas"
        className="w-full h-full bg-brand-gray-medium border border-black"
      >
        <ReactFlow
          nodes={nodes || []}
          edges={edges || []}
          onConnect={onConnect}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          onNodeDragStart={handleNodeDrag}
          onPaneClick={handlePaneClick}
        />
      </div>
    </>
  );
};

export default ReactFlowGraph;
