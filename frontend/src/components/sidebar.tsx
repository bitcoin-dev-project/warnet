import React, { FC } from "react";

import { BITCOIN_CORE_BINARY_VERSIONS } from "@/config";
import { useNodeGraphContext } from "@/contexts/node-graph-context";
import NodePersonaInfo from "./node-persona-info";
import { defaultNodesData } from "@/app/data";

type SidebarProps = {};

const Sidebar: FC<SidebarProps> = ({}) => {
  const { addNode, generateNodeGraph } = useNodeGraphContext();
  return (
    <aside className="flex flex-col items-center justify-center w-2/6 min-h-screen px-4">
      <section className="flex flex-col p-4 h-96 rounded-xl shadow-md border mx-auto text-black bg-white">
        {/* <p className="text-sm font-light mb-2">Add node</p> */}
        {/* <div className="flex gap-4">
          {BITCOIN_CORE_BINARY_VERSIONS.map((version, index) => (
            <button
              key={`${index}-${version}`}
              className="text-[12px] border rounded-md px-2 py-1"
              onClick={() => addNode()}
            >
              {version}
            </button>
          ))}
        </div>
        <div className="border">
          <button
            onClick={() => addNode(defaultNodesData)}
            className="text-sm text-black bg-red font-bold mb-2"
          >
            Add node
          </button>
        </div> */}
        <NodePersonaInfo />
      </section>
      <div className="flex flex-col mt-4 bg-green-200 py-2 px-4 rounded-md hover:bg-green-300">
        <button onClick={generateNodeGraph} className="text-sm text-black bg-red font-semibold">
          generate graph
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
