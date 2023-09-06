'use client';

import React from "react";
import NetworkDialog from "@/components/init-dialog";
import { NodeGraphProvider } from "@/contexts/node-graph-context";
import { NetworkProvider } from "@/contexts/network-context";
import ReactFlowGraph from "@/components/react-flow-graph";
import 'reactflow/dist/style.css';
import { NodeGraphFlowProvider } from "@/contexts/node-flow-context";
export default function Home() {

  return (
    <NetworkProvider>
      {/* <NodeGraphProvider> */}
        <NodeGraphFlowProvider>
        <main className="bg-black flex min-h-screen h-[100vh] items-center justify-center">
          <NetworkDialog />
          {/* <ForceGraph /> */}
          <ReactFlowGraph />
        </main>
        </NodeGraphFlowProvider>
      {/* </NodeGraphProvider> */}
    </NetworkProvider>
  );
}
