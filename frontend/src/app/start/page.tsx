"use client";

import React from "react";
import NetworkDialog from "@/components/init-dialog";
import { NetworkProvider } from "@/contexts/network-context";
import ReactFlowGraph from "@/components/react-flow-graph";
import "reactflow/dist/style.css";
import { NodeGraphFlowProvider } from "@/contexts/node-flow-context";
import { TooltipProvider } from "@radix-ui/react-tooltip";
export default function Home() {
  return (
    <NetworkProvider>
      <NodeGraphFlowProvider>
        <TooltipProvider>
          <main className="bg-black flex min-h-screen h-[100vh] items-center justify-center">
            <NetworkDialog />
            <ReactFlowGraph />
          </main>
        </TooltipProvider>
      </NodeGraphFlowProvider>
    </NetworkProvider>
  );
}
