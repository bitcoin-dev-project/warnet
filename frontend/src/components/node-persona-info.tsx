import React from "react";
import { BITCOIN_CORE_BINARY_VERSIONS, NODE_LATENCY } from "@/config";
import { useNodeFlowContext } from "@/contexts/node-flow-context";

const NodePersonaInfo = () => {
  const { nodePersona } = useNodeFlowContext();

  return (
    <section className={` w-[330px] h-[300px] bg-white rounded-md p-5`}>
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
    </section>
  );
};

export default NodePersonaInfo;
