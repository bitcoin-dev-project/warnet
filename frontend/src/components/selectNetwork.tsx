"use client";

import React, { useRef } from "react";

import { defaultEdgesData, defaultNodesData } from "@/app/data";
import { useNodeGraphContext } from "@/contexts/node-graph-context";
import { NetworkTopology, NodePersonaType, SavedNetworkGraph } from "@/types";
import { CheckIcon, ChevronDownIcon } from "@radix-ui/react-icons";
import * as Select from "@radix-ui/react-select";
import { useNetworkContext } from "@/contexts/network-context";
import { CANVAS_HEIGHT, CANVAS_WIDTH } from "@/config";


const SelectBox = ({list, value, updateSelection}: {list: NetworkTopology[], value: NetworkTopology, updateSelection: (value: NetworkTopology) => void}) => {
  const { setNodePersonaFunc } = useNodeGraphContext();

  const onSelectChange = (value: string) => {
    const network = list.find(network => network.nodePersona.name === value)
    if (!network) return
    updateSelection(network)
  };

  // const containerRef = useRef<HTMLDivElement>(null)
  // const [container, setContainer] = React.useState(null);

  return (
    <Select.Root
      onValueChange={(value) => {
        onSelectChange(value);
      }}
      value={value.nodePersona.name}
      defaultValue={value.nodePersona.name}
    >
      <Select.Trigger
        className="bg-brand-gray-dark w-[280px] inline-flex items-center justify-between px-[15px] text-[13px] leading-none h-[45px] gap-x-[20px] text-brand-text-light shadow-[0_2px_10px] shadow-black/10 hover:bg-brand-gray-light focus:shadow-[0_0_0_2px] focus:shadow-black data-[placeholder]:text-violet9 outline-none"
        aria-label="Node topology"
      >
        <Select.Value
          placeholder="Select a network"
          // defaultValue={value.nodePersona.name}
        />
        <Select.Icon className="">
          <ChevronDownIcon />
        </Select.Icon>
      </Select.Trigger>
      <Select.Portal className="">
        <Select.Content className="mt-[45px] w-full bg-brand-gray-dark overflow-hidden shadow-[0px_10px_38px_-10px_rgba(180,_180,_180,_0.35),0px_10px_20px_-15px_rgba(180,_180,_180,_0.2)]">
          <Select.Viewport className="bg-brand-gray-dark">
            <Select.Group className="flex flex-col bg-brand-gray-dark">
              {list.map((network, idx) => (
                <>
                  <Select.Item
                    key={network.nodePersona.id}
                    value={network.nodePersona.name}
                    className="text-[13px] leading-none text-brand-text-dark flex items-center justify-between px-[15px] h-[35px] relative select-none data-[disabled]:text-green-300 data-[disabled]:pointer-events-none data-[highlighted]:outline-none data-[highlighted]:bg-brand-gray-medium data-[highlighted]:text-brand-text-light"
                  >
                    <Select.ItemText className="text-lg">
                      {network.nodePersona.name}
                    </Select.ItemText>
                    <Select.ItemIndicator className=" w-[25px] inline-flex items-center justify-center">
                      <CheckIcon />
                    </Select.ItemIndicator>
                  </Select.Item>
                  {/* {idx === NetworkTopologyList.length -1 ? null : <Select.Separator className="h-0 border w-[90%] mx-auto border-b-[1px] border-brand-gray-medium" />} */}
                </>
              ))}
            </Select.Group>
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
};

export default SelectBox;
