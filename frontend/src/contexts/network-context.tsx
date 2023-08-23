import React, { useState } from "react";

import { defaultEdgesData, defaultNodesData, tempSavednetwork } from "@/app/data";
import { CANVAS_HEIGHT, CANVAS_WIDTH } from "@/config";
import {
  GraphEdge,
  GraphNode,
  NetworkContext,
  NetworkTopology,
  NodePersona,
  NodePersonaType,
  SavedNetworkGraph,
} from "@/types";
import generateGraphML from "@/helpers/generate-graphml";

const userSteps = {
  "select config": -1,
  "Select network persona": 0,
  "Graph": 1,
} as const;

export type Steps = (typeof userSteps)[keyof typeof userSteps];

export const networkContext = React.createContext<NetworkContext>(null!);

const newNode = {
  id: 0,
  name: "new node",
  size: 10,
  x: CANVAS_WIDTH / 2,
  y: CANVAS_HEIGHT / 2,
};

const newNetworkTopology: NetworkTopology = {
  type: "custom",
  nodePersona: {
    name: "Start from scratch",
    id: 1,
    peers: 0,
    edges: [],
    nodes: [newNode],
    baseFee: 0,
    latency: "0ms",
    version: "22.0",
  },
};

const defaultNetworkTopology: NetworkTopology = {
  type: "prebuilt",
  nodePersona: {
    id: 0,
    name: "Default bitcoin network",
    version: "22.0",
    latency: "10ms",
    peers: 8,
    baseFee: 0.5,
    edges: defaultEdgesData,
    nodes: defaultNodesData,
  },
};

export const NetworkProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const [isDialogOpen, setIsDialogOpen] = useState<boolean>(true);
  // const [showGraph, setShowGraph] = useState<boolean>(false);
  const [selectedNetwork, setSelectedNetwork] = useState(defaultNetworkTopology)
  const [networkList, setNetworkList] = useState<SavedNetworkGraph[]>(
    tempSavednetwork
  )
  
  const networkTopologyList: NetworkTopology[] = [
    defaultNetworkTopology,
    newNetworkTopology,
  ];
  const [steps, setSteps] = React.useState<Steps>(-1);

  const openDialog = () => setIsDialogOpen(true);
  const closeDialog = () => {
    setIsDialogOpen(false);
    setSteps(0);
  };

  const setStep = (step: Steps) => {
    setSteps(step);
  };

  return (
    <networkContext.Provider
      value={{
        steps,
        selectedNetwork,
        setSelectedNetwork,
        isDialogOpen,
        networkList,
        networkTopologyList,
        setNetworkList,
        openDialog,
        closeDialog,
        setStep
      }}
    >
      {children}
    </networkContext.Provider>
  );
};

export const useNetworkContext = () => {
  const context = React.useContext(networkContext);
  if (context === undefined) {
    throw new Error(
      "useNetworkContext must be used within a NetworkProvider"
    );
  }
  return context;
};
