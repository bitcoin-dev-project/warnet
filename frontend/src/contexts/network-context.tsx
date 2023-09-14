import React, { useState } from "react";

import {
  defaultEdgesData,
  defaultNodesData,
  tempSavednetwork,
} from "@/app/data";
import { CANVAS_HEIGHT, CANVAS_WIDTH } from "@/config";
import {
  NetworkContext,
  NetworkTopology,
  SavedNetworkGraph,
} from "@/flowTypes";

export const networkContext = React.createContext<NetworkContext>(null!);

const newNode = {
  id: "0",
  data: {
    id: "0",
    label: "new node",
    size: 10,
  },
  type: "draggable",
  position: {
    x: CANVAS_WIDTH / 2,
    y: CANVAS_HEIGHT / 2,
  },
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
  const [selectedNetwork, setSelectedNetwork] = useState(newNetworkTopology);
  const [networkList, setNetworkList] =
    useState<SavedNetworkGraph[]>(tempSavednetwork);

  const networkTopologyList: NetworkTopology[] = [
    defaultNetworkTopology,
    newNetworkTopology,
  ];

  const openDialog = () => setIsDialogOpen(true);
  const closeDialog = () => {
    setIsDialogOpen(false);
  };

  return (
    <networkContext.Provider
      value={{
        selectedNetwork,
        setSelectedNetwork,
        isDialogOpen,
        networkList,
        networkTopologyList,
        setNetworkList,
        openDialog,
        closeDialog,
      }}
    >
      {children}
    </networkContext.Provider>
  );
};

export const useNetworkContext = () => {
  const context = React.useContext(networkContext);
  if (context === undefined) {
    throw new Error("useNetworkContext must be used within a NetworkProvider");
  }
  return context;
};
