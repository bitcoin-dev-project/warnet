import {
  BITCOIN_CORE_BINARY_VERSIONS,
  CPU_CORES,
  NODE_LATENCY,
  RAM_OPTIONS,
} from "@/config";
import * as Dialog from "@radix-ui/react-dialog";
import React, { useEffect, useState } from "react";
import DefaultSelectBox from "./default-select";
import { useNodeFlowContext } from "@/contexts/node-flow-context";
import { parseBitcoinConf } from "@/helpers/parse-conf-file";
import { InfoCircledIcon } from "@radix-ui/react-icons";
import DefaultTooltip from "./default-tooltip";

const SELECT_BITCOIN_CORE_BINARY_VERSIONS = BITCOIN_CORE_BINARY_VERSIONS.map(
  (version) => ({ name: version, value: version, data: version })
);
const SELECT_NODE_LATENCY = NODE_LATENCY.map((latency) => ({
  name: latency,
  value: latency,
  data: latency,
}));
const BITCOIN_CONF_SELECTION = [
  { name: "Default", value: "default", data: "default" },
];
const SELECT_RAM = RAM_OPTIONS.map((number) => ({
  name: number + "GB",
  value: number.toString(),
  data: number,
}));
const SELECT_CPU_CORES = CPU_CORES.map((number) => ({
  name: number + " Core",
  value: number.toString(),
  data: number,
}));

const NodeInfo = () => {
  const {
    isDialogOpen,
    closeDialog,
    nodeInfo,
    updateNodeInfo,
    saveEditedNode,
  } = useNodeFlowContext();
  const handleDialogOpen = (open: boolean) => {
    if (!open) {
      closeDialog();
    }
  };

  const handleFileChange = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    const name = event.target.files?.[0].name as string;
    let bitcoin_conf;
    if (file) {
      const reader = new FileReader();

      reader.onload = (e: ProgressEvent<FileReader>) => {
        const content = e.target?.result as string;
        bitcoin_conf = parseBitcoinConf(content, name);
        updateNodeInfo("bitcoin_conf", bitcoin_conf);
      };

      reader.readAsText(file);
    }
  };
  return (
    <Dialog.Root open={isDialogOpen} onOpenChange={handleDialogOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="bg-slate-50 opacity-40 data-[state=open]:animate-overlayShow fixed inset-0" />
        <Dialog.Content
          className={`data-[state=open]:animate-contentShow fixed top-1/2 left-1/2
            -translate-x-1/2 -translate-y-1/2 flex flex-col gap-4 p-10 min-h-[300px] max-h-[85vh] w-1/2 max-w-[600px] bg-black shadow-[hsl(206_22%_7%_/_35%)_0px_10px_38px_-10px,_hsl(206_22%_7%_/_20%)_0px_10px_20px_-15px] focus:outline-none`}
        >
          <h2 className="text-4xl mb-4 text-brand-text-light">
            Node Properties
          </h2>
          <section className="flex flex-col gap-4">
            <fieldset className="flex flex-col gap-2 text-[12px] text-brand-text-dark">
              <label>Bitcoin Version</label>
              <DefaultSelectBox
                list={SELECT_BITCOIN_CORE_BINARY_VERSIONS}
                value={nodeInfo?.data?.version}
                placeholder="Select a bitcoin core version"
                updateSelection={(data) => updateNodeInfo("version", data.data)}
              />
              {/* <p>{`Or choose the "start from scratch"`}</p> */}
            </fieldset>
            <fieldset className="flex flex-col gap-2 text-[12px] text-brand-text-dark">
              <label>Latency</label>
              <DefaultSelectBox
                list={SELECT_NODE_LATENCY}
                value={nodeInfo?.data?.latency}
                placeholder="Select node latency"
                updateSelection={(data) => updateNodeInfo("latency", data.data)}
              />
            </fieldset>
            <fieldset className="flex flex-col gap-2 text-[12px] text-brand-text-dark">
              <div className="flex gap-3 items-center">
                <label>Bitcoin.conf selection</label>

                <DefaultTooltip
                  content={
                    <div className="bg-white text-sm py-4 px-4 rounded-sm text-black whitespace-wrap">
                      <p>
                        To generate a bitcoin.conf file please visit{" "}
                        <a
                          href="https://jlopp.github.io/bitcoin-core-config-generator"
                          target="_blank"
                          className="underline font-medium"
                        >
                          jlopp
                        </a>
                      </p>{" "}
                    </div>
                  }
                >
                  <InfoCircledIcon className="cursor-pointer" />
                </DefaultTooltip>
              </div>

              <label
                id="bitcoin_conf_label"
                htmlFor="bitcoin_conf"
                className="flex gap-3 items-center text-brand-text-light w-[280px] bg-brand-gray-dark"
              >
                <p className="bg-blue-600 px-6 py-4 min-w-[120px]">
                  Choose file
                </p>
                <p>
                  {nodeInfo?.data?.bitcoin_conf?.name || "No file selected"}
                </p>
              </label>
              <input
                id="bitcoin_conf"
                type="file"
                onChange={(e) => handleFileChange(e)}
                accept=".conf"
                placeholder="My Network"
                className="h-[45px] px-[15px] w-[280px] hidden file:bg-black border-b-[1px] border-brand-gray-medium bg-brand-gray-dark placeholder:text-sm placeholder:text-brand-text-dark"
              />
            </fieldset>
            <fieldset className="flex flex-col gap-2 text-[12px] text-brand-text-dark">
              <label>RAM</label>
              <DefaultSelectBox
                list={SELECT_RAM}
                value={nodeInfo?.data?.ram?.toString()}
                placeholder="Select RAM size"
                updateSelection={(data) => updateNodeInfo("ram", data.data)}
              />
            </fieldset>
            <fieldset className="flex flex-col gap-2 text-[12px] text-brand-text-dark">
              <label>CPU</label>
              <DefaultSelectBox
                list={SELECT_CPU_CORES}
                value={nodeInfo?.data.cpu?.toString()}
                placeholder="Select CPU core"
                updateSelection={(data) => updateNodeInfo("cpu", data.data)}
              />
            </fieldset>
            <fieldset className="flex flex-col gap-2">
              <label className="text-xs">Node Name</label>
              <input
                id="network_name"
                value={nodeInfo?.data?.label}
                onChange={(e) => updateNodeInfo("label", e.target.value)}
                placeholder="My Network"
                className="h-[45px] px-[15px] w-[280px] border-b-[1px] border-brand-gray-medium bg-brand-gray-dark placeholder:text-sm placeholder:text-brand-text-dark"
              />
            </fieldset>
          </section>
          <div className="max-w-[200px]">
            <button
              className="bg-blue-600 px-6 py-4 min-w-[120px]"
              onClick={saveEditedNode}
            >
              Save
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};

export default NodeInfo;
