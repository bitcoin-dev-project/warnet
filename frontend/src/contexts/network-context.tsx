import React, { useEffect, useState } from "react";

import { tempSavednetwork } from "@/app/data";
import { CANVAS_HEIGHT, CANVAS_WIDTH } from "@/config";
import {
  NetworkContext,
  NetworkTopology,
  SavedNetworkGraph,
} from "@/flowTypes";
import { readXML } from "@/helpers/generate-network-from-graphml";

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

export const NetworkProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const [isDialogOpen, setIsDialogOpen] = useState<boolean>(true);
  const [selectedNetwork, setSelectedNetwork] = useState(newNetworkTopology);
  const [networkList, setNetworkList] =
    useState<SavedNetworkGraph[]>([]);

  // async function feet() {
  //   const res = await fetch("graphml/wheel_graph_n100_pos.graphml");
  //   console.log(res);
  // }
  // feet();
  useEffect(() => {
    async function getGraphDetails() {
      for (const network of tempSavednetwork) {
        if (network.graphmlPath) {
          const {nodes, edges} = await readXML(network.graphmlPath)
          if (nodes?.length && edges?.length) {
            const builtNetwork: SavedNetworkGraph = {
              ...network,
              nodePersona: {
                ...network.nodePersona,
                peers: nodes.length,
                nodes,
                edges
              }
            }
            setNetworkList(prev => ([...prev, builtNetwork]))
          }
        }
        if (network.type === "custom" && !network.graphmlPath) {
          setNetworkList(prev => ([...prev, network]))
        }
      }
    }
    getGraphDetails()
    return () => {};
  }, []);

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
