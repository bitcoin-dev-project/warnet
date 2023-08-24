"use client";

import React from "react";

import { useNetworkContext } from "@/contexts/network-context";
import { useNodeGraphContext } from "@/contexts/node-graph-context";
import * as Dialog from "@radix-ui/react-dialog";
import SelectBox from "./selectNetwork";

const NetworkDialog = () => {
  const { isDialogOpen, closeDialog, openDialog, steps, networkList, setStep, networkTopologyList, selectedNetwork, setSelectedNetwork } =
    useNetworkContext();
  const {setNodePersonaFunc, showGraphFunc} = useNodeGraphContext()

  const graphNextStep = () => {
    setNodePersonaFunc({type: selectedNetwork.type, nodePersona: selectedNetwork.nodePersona})
    showGraphFunc()
    closeDialog()
  }


  const NetworkList = () => {
    return (
      <>
      <Dialog.Root open={isDialogOpen && steps === -1}>
        <Dialog.Trigger
          onClick={openDialog}
          className="text-brand-text-dark shadow-blackA7 hover:bg-mauve3 inline-flex h-[35px] items-center justify-center rounded-[4px] bg-white px-[15px] font-medium leading-none shadow-[0_2px_10px] focus:shadow-[0_0_0_2px] focus:shadow-black focus:outline-none"
        >
          Build your node profile
        </Dialog.Trigger>
        <Dialog.Portal>
          <Dialog.Overlay className="bg-slate-50 opacity-10 data-[state=open]:animate-overlayShow fixed inset-0" />
          <Dialog.Content
            className={`data-[state=open]:animate-contentShow fixed top-1/2 left-1/2
            -translate-x-1/2 -translate-y-1/2 flex flex-col justify-center min-h-[300px] max-h-[85vh] w-[90vw] max-w-[800px] bg-brand-gray-dark shadow-[hsl(206_22%_7%_/_35%)_0px_10px_38px_-10px,_hsl(206_22%_7%_/_20%)_0px_10px_20px_-15px] focus:outline-none`}
          >
            <Dialog.Title className="text-brand-text-light text-xl px-4 pt-2">
              Network Topology Configurations
            </Dialog.Title>
            <Dialog.Description className="text-brand-text-dark px-4 py-2 text-sm leading-normal">
              These network topology configs can be used to generate a local
              warnet with warnet-cli
            </Dialog.Description>
            <button className="ml-auto bg-blue-600 p-4" onClick={() => setStep(0)}>
              Create New Config +
            </button>
            <table className="init_dialog_table_config">
              <thead className="bg-brand-gray-medium text-brand-text-light font-semibold text-sm">
                <tr className="h-[60px] text-left">
                  <th>Name</th>
                  <th># of Nodes</th>
                  <th>Date created</th>
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
                        <td>{network.nodePersona?.nodes.length}</td>
                        <td>{network.date.toISOString()}</td>
                        <td>Actions</td>
                      </tr>
                    );
                  })
                ) : (
                  <div className="py-8 w-full flex justify-center">
                    <button className="ml-auto bg-blue-600 p-4" onClick={() => setStep(0)}>
                      Create New Config +
                    </button>
                  </div>
                )}
              </tbody>
            </table>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      </>
    );
  }

  const NetworkTopology = () => {
    return (
      <Dialog.Root open={isDialogOpen && steps === 0}>
        <Dialog.Portal>
          <Dialog.Overlay className="bg-slate-50 opacity-10 data-[state=open]:animate-overlayShow fixed inset-0" />
          <Dialog.Content
            className={`data-[state=open]:animate-contentShow fixed top-1/2 left-1/2
            -translate-x-1/2 -translate-y-1/2 flex flex-col p-10 min-h-[300px] max-h-[85vh] w-[90vw] max-w-[800px] bg-black shadow-[hsl(206_22%_7%_/_35%)_0px_10px_38px_-10px,_hsl(206_22%_7%_/_20%)_0px_10px_20px_-15px] focus:outline-none`}
          >
            <fieldset className="flex flex-col gap-2 text-[12px] text-brand-text-dark">
              <label>Select a network topology</label>
              <div>
                <SelectBox list={networkTopologyList} updateSelection={setSelectedNetwork} value={selectedNetwork} />
              </div>
              <p>{`Or choose the "start from scratch"`}</p>
            </fieldset>
            <div className="mt-8 max-w-[200px]">
              <button className="bg-blue-600 px-6 py-4 min-w-[120px]" onClick={graphNextStep}>
                Select
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    );
  }

  switch (steps) {
    case -1:
      return <NetworkList />
    case 0:
      return <NetworkTopology />
    default:
      return null
  }
};

export default NetworkDialog;
