import React, { FC } from "react";

import { BITCOIN_CORE_BINARY_VERSIONS } from "@/config";
import { useNodeGraphContext } from "@/contexts/node-graph-context";
import NodePersonaInfo from "./node-persona-info";
import { defaultNodesData } from "@/app/data";
import NodeList from "./node-list";
import { NetworkTopology, NodePersona } from "@/types";

type SidebarProps = {};

const testPersona: NetworkTopology = {
  type: "custom",
  nodePersona: {
    baseFee: 0.5,
    id: 12,
    latency: "10ms",
    name: "test",
    nodes: [
      {
        size: 10,
        id: 0,
        name: "first",
        latency: "10ms",
        version: "21.0",
      },
      {
        size: 10,
        id: 1,
        name: "second",
        latency: "10ms",
        version: "21.0",
      },
    ],
    edges: [
      {
        source: 0,
        target: 1,
      },
    ],
    peers: 2,
    version: "22.0",
  },
};

const Sidebar: FC<SidebarProps> = ({}) => {
  const { addNode, generateNodeGraph } =
    useNodeGraphContext();
  
  const addNewNode = () => {
    addNode()
  }
  return (
    <aside className="flex flex-col w-2/6 h-full px-4">
      <h2 className="mt-4 text-brand-text-light text-2xl font-light">
        Network Topology
      </h2>
      <section className="w-full flex flex-col gap-8 mt-8 text-brand-text-dark">
        <fieldset className="flex flex-col gap-2">
          <label htmlFor="network_name" className="text-xs">
            Network Name
          </label>
          <input
            id="network_name"
            placeholder="My Network"
            className="h-[45px] w-full border-b-[1px] border-brand-gray-medium bg-brand-gray-dark placeholder:px-2 placeholder:text-sm"
          />
        </fieldset>
        <div>
          <button onClick={addNewNode} className="h-[45px] text-[13px] px-4 border-b-[1px] border-brand-gray-medium disabled:bg-brand-text-dark disabled:text-brand-text-light bg-brand-gray-medium">
            Add Node +
          </button>
        </div>
        <NodeList />
      </section>
      <div className="flex flex-col mt-4 bg-green-200 py-2 px-4 rounded-md hover:bg-green-300">
        <button
          onClick={generateNodeGraph}
          className="text-sm text-black font-semibold"
        >
          generate graph
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
