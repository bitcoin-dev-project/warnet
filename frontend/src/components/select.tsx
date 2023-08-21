"use client";

import React from "react";

import { defaultEdgesData, defaultNodesData } from "@/app/data";
import { useNodeGraphContext } from "@/contexts/node-graph-context";
import { NodePersonaType } from "@/types";
import { CheckIcon, ChevronDownIcon } from "@radix-ui/react-icons";
import * as Select from "@radix-ui/react-select";

const SelectBox = () => {
  const { nodes, edges, setNodePersonaFunc, addNode, setNodeEdges } =
    useNodeGraphContext();

  const setNodePersona = (value: NodePersonaType) => {
    setNodePersonaFunc(value as NodePersonaType);
    if (value === "prebuilt" && edges.length === 0 && nodes.length === 0) {
      addNode(defaultNodesData);
      setNodeEdges(defaultEdgesData);
    }
  };

  return (
    <Select.Root
      onValueChange={(value) => {
        setNodePersona(value as NodePersonaType);
      }}
    >
      <Select.Trigger
        className="w-[280px] border inline-flex items-center justify-center rounded px-[15px] text-[13px] leading-none h-[35px] gap-x-[20px] bg-white text-slate-900 shadow-[0_2px_10px] shadow-black/10 hover:bg-slate-50 focus:shadow-[0_0_0_2px] focus:shadow-black data-[placeholder]:text-violet9 outline-none"
        aria-label="Node topology"
      >
        <Select.Value placeholder="Select a node topology..." />
        <Select.Icon className="text-slate-900">
          <ChevronDownIcon />
        </Select.Icon>
      </Select.Trigger>
      <Select.Portal className="mt-[50px]">
        <Select.Content className="overflow-hidden bg-white rounded-md shadow-[0px_10px_38px_-10px_rgba(22,_23,_24,_0.35),0px_10px_20px_-15px_rgba(22,_23,_24,_0.2)]">
          <Select.Viewport className="p-[5px]">
            <Select.Group className="flex flex-col gap-y-1">
              <Select.Label className="px-[25px] text-xs leading-[25px] text-black">
                Node personas
              </Select.Label>
              <Select.Item
                value="custom"
                className="relative text-[13px] leading-none text-violet-500 rounded-[3px] flex items-center h-[25px] pr-[35px] pl-[25px] select-none data-[disabled]:text-green-300 data-[disabled]:pointer-events-none data-[highlighted]:outline-none data-[highlighted]:bg-violet-50 data-[highlighted]:text-violet-600"
              >
                <Select.ItemText className="text-black text-lg">
                  Create your own node topology
                </Select.ItemText>
                <Select.ItemIndicator className="absolute left-0 w-[25px] inline-flex items-center justify-center">
                  <CheckIcon />
                </Select.ItemIndicator>
              </Select.Item>
              <Select.Item
                value="prebuilt"
                className="text-[13px] leading-none text-violet-500 rounded-[3px] flex items-center h-[25px] pr-[35px] pl-[25px] relative select-none data-[disabled]:text-green-300 data-[disabled]:pointer-events-none data-[highlighted]:outline-none data-[highlighted]:bg-violet-50 data-[highlighted]:text-violet-600"
              >
                <Select.ItemText className="text-black text-lg">
                  Use a pre-built node topology
                </Select.ItemText>
                <Select.ItemIndicator className="absolute left-0 w-[25px] inline-flex items-center justify-center">
                  <CheckIcon />
                </Select.ItemIndicator>
              </Select.Item>
            </Select.Group>
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
};

export default SelectBox;
