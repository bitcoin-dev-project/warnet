"use client";
import React from "react";

import { useNetworkContext } from "@/contexts/network-context";
import { useNodeFlowContext } from "@/contexts/node-flow-context";
import { SavedNetworkGraph } from "@/flowTypes";
import downloadGraph from "@/helpers/download-graphml";
import generateGraphML from "@/helpers/generate-graphml";
import Link from "next/link";

const NetworkDialog = () => {
  const { isDialogOpen, networkList } = useNetworkContext();

  const handleDownloadGraph = (network: SavedNetworkGraph) => {
    if (network.type === "prebuilt" && network.graphmlPath) {
      downloadGraph(network.graphmlPath);
    } else
      generateGraphML({
        nodes: network.nodePersona.nodes,
        edges: network.nodePersona.edges,
      });
  };

  if (!isDialogOpen) return null;

  const NetworkList = () => {
    return (
      <>
        <div
          className={`data-[state=open]:animate-contentShow fixed top-1/2 left-1/2
            -translate-x-1/2 -translate-y-1/2 flex flex-col justify-center min-h-[300px] max-h-[85vh] w-[90vw] max-w-[800px] bg-brand-gray-dark shadow-[hsl(206_22%_7%_/_35%)_0px_10px_38px_-10px,_hsl(206_22%_7%_/_20%)_0px_10px_20px_-15px] focus:outline-none`}
        >
          <h1 className="text-brand-text-light text-xl px-4 pt-2">
            Network Topology Configurations
          </h1>
          <p className="text-brand-text-dark px-4 py-2 text-sm leading-normal">
            These network topology configs can be used to generate a local
            warnet with warnet-cli
          </p>
          <Link className="ml-auto bg-blue-600 p-4" href={`?network=new`}>
            Create New Config +
          </Link>
          <table className="init_dialog_table_config">
            <thead className="bg-brand-gray-medium text-brand-text-light font-semibold text-sm">
              <tr className="h-[60px] text-left">
                <th>Name</th>
                <th># of Nodes</th>
                {/* <th>Date created</th> */}
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {networkList.length ? (
                networkList.map((network) => {
                  return (
                    <tr
                      key={network.nodePersona?.id}
                      className="font-normal text-sm text-brand-text-dark h-[40px]"
                    >
                      <td>{network.nodePersona?.name}</td>
                      <td>{network.nodePersona.peers}</td>
                      {/* <td>{network.date.toISOString()}</td> */}
                      <td className="w-[30%]">
                        <div className="flex flex-wrap gap-4">
                          <Link
                            className="flex-grow border border-brand-gray-light px-4 py-2 min-w-[80px] text-white capitalize"
                            href={`?network=${network.nodePersona.name}`}
                          >
                            edit
                          </Link>
                          {/* <button
                            className="flex-grow border border-brand-gray-light px-4 py-2 min-w-[80px] text-white capitalize"
                            onClick={() => graphNextStep(network)}
                          >
                            edit
                          </button> */}
                          <button
                            onClick={() => handleDownloadGraph(network)}
                            className="bg-blue-600 px-4 py-2 min-w-[80px] text-white capitalize"
                          >
                            download
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <>
                  <tr>
                    <td className="absolute w-full flex justify-center">
                      <div className="py-8 flex justify-center">
                        <Link
                          className="ml-auto bg-blue-600 p-4"
                          href={`?network=new`}
                        >
                          Create New Config +
                        </Link>
                      </div>
                    </td>
                  </tr>
                  <tr className="h-[120px]"></tr>
                </>
              )}
            </tbody>
          </table>
        </div>
      </>
    );
  };

  return <NetworkList />;
};

export default NetworkDialog;
