import React, { useState, useEffect } from "react";
import { CANVAS_HEIGHT, CANVAS_WIDTH } from "@/config";
import {
  GraphEdge,
  GraphNode,
  NetworkTopology,
  NodeGraphContext,
  NodePersona,
  NodePersonaType,
} from "@/flowTypes";
import { defaultNodePersona } from "@/app/data";
import { v4 } from "uuid";
import { Edge, Node, useEdgesState, useNodesState } from "reactflow";
import generateGraphML from "@/helpers/generate-graphml";
export const nodeFlowContext = React.createContext<NodeGraphContext>(null!);

export const NodeGraphFlowProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const [isDialogOpen, setIsDialogOpen] = useState<boolean>(false);
  const [showGraph, setShowGraph] = useState<boolean>(false);
  const [nodes, setNodes, onNodesChange] = useNodesState<GraphNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<GraphEdge>([]);
  const [nodePersonaType, setNodePersonaType] =
    useState<NodePersonaType | null>(null);
  const [nodePersona, setNodePersona] = useState<NodePersona | null>(
    defaultNodePersona
  );
  const [nodeInfo, setNodeInfo] = useState<Node<GraphNode> | null>(null);
  const openDialog = () => setIsDialogOpen(true);
  const closeDialog = () => {
    setIsDialogOpen(false);
    setNodeInfo(null);
  };

  const setNodePersonaFunc = ({ type, nodePersona }: NetworkTopology) => {
    setNodePersonaType(type);
    setNodePersona(nodePersona);
    setNodes(nodePersona.nodes);
    setNodeEdges(nodePersona.edges);
  };

  const showGraphFunc = () => {
    // setSteps(2);
    setShowGraph(true);
  };

  const showNodePersonaInfo = () => {
    // setSteps(1);
  };

  const setNodeEdges = (edge: Edge<GraphEdge>[]) => {
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
    const newNodesNumber = nodes.filter(
      (node) => node.data?.label?.includes("new node")
    ).length;
    const id = (nodes[nodes.length - 1]?.id ?? 0) + 1;
    const newNode: Node<GraphNode> = {
      id,
      data: {
        id,
        label: "new node " + newNodesNumber,
        size: 10,
      },
      type: "draggable",
      position: {
        x: CANVAS_WIDTH / 2,
        y: CANVAS_HEIGHT / 2,
      },
    };
    return newNode;
  };

  const addNode = (node?: Node<GraphNode>) => {
    const newNode = node ? node : createNewNode();
    setNodes([...nodes, newNode]);
    setNodeInfo(newNode);
    openDialog();
  };

  const editNode = (node: Node<GraphNode>) => {
    setNodeInfo(node)
    openDialog();
  };

  const duplicateNode = (node: Node<GraphNode>) => {
    const id = (nodes[nodes.length - 1]?.id ?? 0) + 1;
    const length = nodes.length;
    const duplicateNode = {
      ...node,
      id,
      data: {
        ...node.data,
        id,
        label: `${node?.data?.label} duplicate`,
      },
    };
    addNode(duplicateNode);
  };

  const updateNodeInfo = (nodeProperty: any, value: any) => {
    if (!nodeInfo) return;
    const duplNode = JSON.parse(JSON.stringify(nodeInfo));
    duplNode.data[nodeProperty] = value;
    setNodeInfo(duplNode);
  };

  const saveEditedNode = () => {
    if (!nodeInfo) return;
    const nodeIndex = nodes.findIndex((node) => node.id === nodeInfo?.id);
    if (nodeIndex !== -1) {
      const newList = [...nodes];
      newList[nodeIndex] = nodeInfo;
      setNodes(newList);
      closeDialog();
    }
  };

  const deleteNode = (node: Node<GraphNode>) => {
    const updatedNodes = nodes.filter(({ id }) => id !== node.id);
    const newEdges = edges.filter(({ source, target }) => {
      // remove edge if source or target is linked to the node
      return !(source === node.id || target === node.id);
    });
    setEdges(newEdges);
    setNodes(updatedNodes);
  };

  return (
    <nodeFlowContext.Provider
      value={{
        nodes,
        edges,
        setEdges,
        setNodes,
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
        onNodesChange,
        onEdgesChange,
      }}
    >
      {children}
    </nodeFlowContext.Provider>
  );
};

export const useNodeFlowContext = () => {
  const context = React.useContext(nodeFlowContext);
  if (context === undefined) {
    throw new Error(
      "useNodeFlowContext must be used within a NodeFlowProvider"
    );
  }
  return context;
};
