import React, { useState, useEffect } from "react";
import { CANVAS_HEIGHT, CANVAS_WIDTH } from "@/config";
import {
  GraphEdge,
  GraphNode,
  NetworkTopology,
  NodeGraphContext,
  NodePersona,
  NodePersonaType,
} from "@/types";
import generateGraphML from "@/helpers/generate-graphml";
import { defaultNodePersona } from "@/app/data";

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
  const [nodeInfo, setNodeInfo] = useState<GraphNode | null>(null)
  const openDialog = () => setIsDialogOpen(true);
  const closeDialog = () => {
    setIsDialogOpen(false);
    setNodeInfo(null)
    // setSteps(-1);
  };

  const setNodePersonaFunc = ({type, nodePersona}: NetworkTopology) => {
    setNodePersonaType(type)
    setNodePersona(nodePersona)
    setNodes(nodePersona.nodes)
    setNodeEdges(nodePersona.edges)
  };

  const showGraphFunc = () => {
    // setSteps(2);
    setShowGraph(true);
  };

  // const setStep = (step: Steps) => {
  //   setSteps(step);
  // };

  const showNodePersonaInfo = () => {
    // setSteps(1);
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

  const createNewNode = () => {
    const newNodesNumber = nodes.filter(node => node.name?.includes("new node")).length
    const newNode =
      {
        id: nodes.length,
        name: "new node " + newNodesNumber,
        size: 10,
        x: CANVAS_WIDTH / 2,
        y: CANVAS_HEIGHT / 2,
      }
    return newNode;
  }

  const addNode = (node?: GraphNode) => {
    const newNode = node ? node : createNewNode()
    setNodes([...nodes, newNode]);
    setNodeInfo(newNode)
    openDialog()
  };

  const editNode = (node: GraphNode) => {
    setNodeInfo(node)
    openDialog()
  }
  
  const duplicateNode = (node: GraphNode) => {
    const duplicateNode = {...node}
    duplicateNode["id"] = nodes.length
    duplicateNode["name"] = node.name + " duplicate"
    addNode(duplicateNode)
  }

  const updateNodeInfo = <K extends keyof GraphNode>(nodeProperty: K, value: GraphNode[K]) => {
    if (!nodeInfo) return
    const duplNode = {...nodeInfo}
    duplNode![nodeProperty] = value
    setNodeInfo(duplNode)
  }

  const saveEditedNode = () => {
    if (!nodeInfo) return;
    const nodeIndex = nodes.findIndex((node) => node.id === nodeInfo?.id)
    if (nodeIndex !== -1) {
      const newList = [...nodes]
      const newEdges = [...edges]
      newList[nodeIndex] = nodeInfo
      const strippedEdges = newEdges.map(({source, target}) => ({source: source.id, target: target.id}))
      setNodes(newList)
      setEdges(strippedEdges)
      closeDialog()
    }
  }

  const deleteNode = (node: GraphNode) => {
    const updatedNodes = nodes.filter(({ id }) => id !== node.id)
    const newEdges = edges.filter(({source, target}) => {
      // remove edge if source or target is linked to the node
      return !(source.id === node.id || target.id === node.id)
    })
    setEdges(newEdges)
    setNodes(updatedNodes)
  }

  function stripEdges(edges: GraphEdge[]) {
    return edges.map(({source, target}) => ({source: source.id, target: target.id}))
  }

  // React.useEffect(() => {
  //   console.log("nodes", nodes);
  //   console.log("edges", edges);
  // }, [nodes, edges]);

  return (
    <nodeGraphContext.Provider
      value={{
        nodes,
        edges,
        nodePersona,
        nodePersonaType,
        isDialogOpen,
        showGraph,
        nodeInfo,
        updateNodeInfo,
        editNode,
        saveEditedNode,
        // setNodeInfo,
        showGraphFunc,
        openDialog,
        closeDialog,
        addNode,
        duplicateNode,
        deleteNode,
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
