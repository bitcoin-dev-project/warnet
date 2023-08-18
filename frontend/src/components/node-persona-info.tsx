import React from "react";

import { useNodeGraphContext } from "@/contexts/node-graph-context";
import { BITCOIN_CORE_BINARY_VERSIONS, NODE_LATENCY } from "@/config";
import { defaultEdgesData, defaultNodesData } from "@/app/data";
import AccordionDemo from "./node-accordion";

const NodePersonaInfo = () => {
  const {
    nodePersonaType,
    nodePersona,
    steps,
    closeDialog,
    showGraphFunc,
  } = useNodeGraphContext();

  if (!nodePersonaType || steps !== 1) {
    return null;
  }

  return (
    <section
      className={`fixed right-[-100%] top-[-80%] translate-y-[50%] w-[330px] h-[300px] bg-white rounded-md p-5`}
    >
      <div className="fixed left-[-50%] top-[35%] w-[100%] h-[1px] bg-white -z-10"></div>
      <p className="text-sm text-black font-light mb-2">core version</p>
      <fieldset className="flex gap-3 mb-4">
        {BITCOIN_CORE_BINARY_VERSIONS.map((version, index) => (
          <button
            key={`${index}-${version}`}
            className={`flex items-center justify-center text-[12px] text-black border rounded-md min-w-[45px] px-2 py-1 cursor-pointer hover:bg-slate-100 ${
              version === nodePersona?.version && "bg-slate-200"
            }`}
            onClick={() => console.log("clicked", version)}
          >
            {version}
          </button>
        ))}
      </fieldset>
      <fieldset>
        <p className="text-sm text-black font-light mb-2">latency</p>
        <div className="flex gap-3 mb-4">
          {NODE_LATENCY.map((latency, index) => (
            <button
              key={`${index}-${latency}`}
              className={`flex items-center justify-center text-[12px] text-black border rounded-md min-w-[45px] px-2 py-1 cursor-pointer hover:bg-slate-100 ${
                latency === nodePersona?.latency ? "bg-slate-200" : ""
              }`}
              onClick={() => console.log("clicked", latency, nodePersona)}
            >
              {latency}
            </button>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <p className="text-sm text-black font-light mb-2">peers</p>{" "}
        <div className="flex gap-3 mb-4">
          {[0, 2, 4, 8, 10].map((index) => (
            <button
              key={`${index}-${index}`}
              className={`flex items-center justify-center text-[12px] text-black border rounded-md min-w-[45px] px-2 py-1 cursor-pointer hover:bg-slate-100 ${
                index === 4 && "bg-slate-200"
              }`}
              onClick={() => console.log("clicked", nodePersona)}
            >
              {index}
            </button>
          ))}
        </div>
      </fieldset>
      <AccordionDemo />
      <div className="flex justify-end">
        <button
          onClick={() => {
            closeDialog();
            showGraphFunc();
          }}
          className="bg-green-100 text-green-700 hover:bg-green5 focus:shadow-green7 inline-flex h-[35px] items-center justify-center rounded-[4px] px-[15px] font-medium leading-none focus:shadow-[0_0_0_2px] focus:outline-none"
        >
          Next
        </button>
      </div>
    </section>
  );
};

export default NodePersonaInfo;
