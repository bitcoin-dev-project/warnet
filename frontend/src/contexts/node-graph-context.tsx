import React, { useState } from "react";

import { defaultEdgesData, defaultNodesData } from "@/app/data";
import { CANVAS_HEIGHT, CANVAS_WIDTH } from "@/config";
import {
  GraphEdge,
  GraphNode,
  NodeGraphContext,
  NodePersona,
  NodePersonaType,
} from "@/types";
import generateGraphML from "@/helpers/generate-graphml";

const defaultNodePersona: NodePersona = {
  id: 0,
  name: "Alice",
  version: "22.0",
  latency: "10ms",
  peers: 8,
  baseFee: 0.5,
  edges: defaultEdgesData,
  nodes: defaultNodesData,
};

const userSteps = {
  "build your node profile": -1,
  "Select a persona": 0,
  "Show node persona info": 1,
  "Add a node": 2,
} as const;

export type Steps = (typeof userSteps)[keyof typeof userSteps];

export const nodeGraphContext = React.createContext<NodeGraphContext>(null!);

export const NodeGraphProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const [isDialogOpen, setIsDialogOpen] = useState<boolean>(false);
  const [showGraph, setShowGraph] = useState<boolean>(false);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [nodePersonaType, setNodePersonaType] =
    useState<NodePersonaType | null>(null);
  const [nodePersona, setNodePersona] = useState<NodePersona | null>(
    defaultNodePersona
  );
  const [steps, setSteps] = React.useState<Steps>(-1);

  const openDialog = () => setIsDialogOpen(true);
  const closeDialog = () => {
    setIsDialogOpen(false);
    setSteps(-1);
  };

  const setNodePersonaFunc = (persona: NodePersonaType) => {
    setNodePersonaType(persona), console.log("persona", persona);
  };

  const showGraphFunc = () => {
    setSteps(2);
    setShowGraph(true);
  };

  const setStep = (step: Steps) => {
    setSteps(step);
  };

  const showNodePersonaInfo = () => {
    setSteps(1);
  };

  const setNodeEdges = (edge: GraphEdge[]) => {
    setEdges([...edge]);
  };

  const generateNodeGraph = () => {
    // const nodeGraph = {
    //   nodes: nodes,
    //   edges: edges,
    // };
    generateGraphML({ nodes, edges });
  };

  const addNode = (nodeArray?: GraphNode[]) => {
    if (nodeArray) {
      setNodes([...nodes, ...nodeArray]);
      return;
    }
    const newNode = [
      {
        id: nodes.length,
        name: "new node",
        size: 10,
        x: CANVAS_WIDTH / 2,
        y: CANVAS_HEIGHT / 2,
      },
    ];
    console.log("newNode", newNode);
    setNodes([...nodes, ...newNode]);
  };

  React.useEffect(() => {
    console.log("nodes", nodes);
    console.log("edges", edges);
  }, [nodes, edges]);

  return (
    <nodeGraphContext.Provider
      value={{
        steps,
        nodes,
        edges,
        nodePersona,
        nodePersonaType,
        isDialogOpen,
        showGraph,
        showGraphFunc,
        openDialog,
        closeDialog,
        addNode,
        setStep,
        setNodePersonaFunc,
        showNodePersonaInfo,
        setNodeEdges,
        generateNodeGraph,
      }}
    >
      {children}
    </nodeGraphContext.Provider>
  );
};

export const useNodeGraphContext = () => {
  const context = React.useContext(nodeGraphContext);
  if (context === undefined) {
    throw new Error(
      "useNodeGraphContext must be used within a NodeGraphProvider"
    );
  }
  return context;
};
