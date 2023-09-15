import React, { useState, useEffect, useRef, useCallback } from "react";
import { CANVAS_HEIGHT, CANVAS_WIDTH } from "@/config";
import {
  GraphEdge,
  GraphNode,
  NetworkTopology,
  NodeGraphContext,
  NodePersona,
  NodePersonaType,
  SavedNetworkGraph,
} from "@/flowTypes";
import { defaultNodePersona, newNetwork, tempSavednetwork } from "@/app/data";
import { v4 } from "uuid";
import { Edge, Node, useEdgesState, useNodesState, Position } from "reactflow";
import generateGraphML from "@/helpers/generate-graphml";
import dagre from "@dagrejs/dagre";
// import { useRouter } from "next/router";
import { useRouter, useSearchParams } from "next/navigation";
import { useNetworkContext } from "./network-context";
import { readXML } from "@/helpers/generate-network-from-graphml";

export const nodeFlowContext = React.createContext<NodeGraphContext>(null!);

export const NodeGraphFlowProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const [isDialogOpen, setIsDialogOpen] = useState<boolean>(false);
  // const [showGraph, setShowGraph] = useState<boolean>(false);
  const [nodes, setNodes, onNodesChange] = useNodesState<GraphNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<GraphEdge>([]);
  const [nodePersonaType, setNodePersonaType] =
    useState<NodePersonaType | null>(null);
  const [nodePersona, setNodePersona] = useState<NodePersona | null>(null);
  const [nodeInfo, setNodeInfo] = useState<Node<GraphNode> | null>(null);
  const openDialog = () => setIsDialogOpen(true);
  const closeDialog = () => {
    setIsDialogOpen(false);
  };

  const hasForcedGraph = useRef(false)

  const { networkList } = useNetworkContext();

  const router = useRouter()
  const searchParams = useSearchParams();
  const networkQuery = searchParams.get("network");
  const showGraph = Boolean(networkQuery);

  function reset() {
    setIsDialogOpen(false)
    setNodes([])
    setEdges([])
    setNodePersonaType(null)
    setNodeInfo(null)
    setNodePersona(null)
  }

  async function getGraphDetails(network: SavedNetworkGraph) {
    if (network.graphmlPath) {
      const { nodes, edges } = await readXML(network.graphmlPath);
      if (nodes?.length && edges?.length) {
        const builtNetwork: SavedNetworkGraph = {
          ...network,
          nodePersona: {
            ...network.nodePersona,
            peers: nodes.length,
            nodes,
            edges,
          },
        };
        return builtNetwork;
      }
    }
  }

  useEffect(() => {
    async function processPrebuiltGraph (network: SavedNetworkGraph) {
      const graphDetails = await getGraphDetails(network)
      if (graphDetails?.nodePersona.nodes.length) {
        setNodePersonaFunc({
          type: graphDetails.type,
          nodePersona: graphDetails.nodePersona,
        });
      }
    }

    if (networkQuery) {
      if (networkQuery === "new") {
        setNodePersonaFunc({
          type: newNetwork.type,
          nodePersona: newNetwork.nodePersona
        })
      }
      const selectedNetwork = networkList.find(
        (network) => network.nodePersona.name === networkQuery
      );

      if (!selectedNetwork) {
        router.push("?network=new")
      }

      if (selectedNetwork?.type === "prebuilt") {
        processPrebuiltGraph(selectedNetwork)
      } else if (selectedNetwork?.type === "custom") {
        setNodePersonaFunc({
          type: selectedNetwork.type,
          nodePersona: selectedNetwork.nodePersona,
        });
        if (!hasForcedGraph.current) {
          forceGraph({
            provisionedNodes: selectedNetwork.nodePersona.nodes,
            provisionedEdges: selectedNetwork.nodePersona.edges
          })
        }
      } else {
        return
      }
    } else {
      reset()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [networkQuery, networkList]);

  

  const forceGraph = useCallback((optional?: {
    provisionedNodes: Node<GraphNode>[],
    provisionedEdges: Edge<GraphEdge>[],
  }) => {
    // don't force graph for prebuilt topologies
    if (nodePersonaType === "prebuilt") return;

    let internalNodes = optional?.provisionedNodes ?? nodes
    let internalEdges = optional?.provisionedEdges ?? edges
    if (!internalNodes.length) return;


    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));

    dagreGraph.setGraph({ rankdir: "LR" });

    internalNodes.forEach((node) => {
      dagreGraph.setNode(node.id, { width: 150, height: 50 });
    });

    internalEdges.forEach((edge) => {
      dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    hasForcedGraph.current = true

    const layoutedNodes = internalNodes.map((node) => {
      const nodeWithPosition = dagreGraph.node(node.id);
      node.targetPosition = Position.Left;
      node.sourcePosition = Position.Right;
      // we need to pass a slightly different position in order to notify react flow about the change
      // @TODO how can we change the position handling so that we dont need this hack?
      node.position = {
        x: nodeWithPosition.x + Math.random() / 1000,
        y: nodeWithPosition.y,
      };

      return node;
    });

    setNodes(layoutedNodes);
  }, [nodes, edges]);

  function setNodePersonaFunc({ type, nodePersona }: NetworkTopology) {
    setNodePersonaType(type);
    setNodePersona(nodePersona);
    setNodes(nodePersona.nodes);
    setEdges(nodePersona.edges);
  };

  const showGraphFunc = () => {
    // setSteps(2);
    // setShowGraph(true);
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

  const selectNode = (id: Node["id"] | null) => {
    if (!id) {
      setNodeInfo(null);
      return;
    }
    const node = nodes.find((_node) => _node.id === id);
    if (node) {
      setNodeInfo(node);
    }
  };

  const editNode = (node: Node<GraphNode>) => {
    setNodeInfo(node);
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
        selectNode,
        forceGraph,
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
