"use client";

import React from "react";
import { CheckIcon, ChevronDownIcon } from "@radix-ui/react-icons";
import * as Select from "@radix-ui/react-select";

type DefaultSelectType<T> = {
  name: string;
  value: string;
  data?: T;
}

type SelectProps<T> = {
  placeholder: string;
  list: DefaultSelectType<T>[];
  value?: string;
  defaultValue?: string;
  updateSelection: (value: DefaultSelectType<T>) => void
}

const DefaultSelectBox = <T extends unknown>({list, value, updateSelection, defaultValue, placeholder}: SelectProps<T>) => {

  const onSelectChange = (value: string) => {
    const selectedItem = list.find(item => item.value === value)
    if (!selectedItem) return
    updateSelection(selectedItem)
  };

  return (
    <Select.Root
      onValueChange={(value) => {
        onSelectChange(value);
      }}
      value={value ?? undefined}
      defaultValue={defaultValue ?? undefined}
    >
      <Select.Trigger
        className="bg-brand-gray-dark w-[280px] inline-flex items-center justify-between px-[15px] text-[13px] leading-none h-[45px] gap-x-[20px] text-brand-text-light shadow-[0_2px_10px] shadow-black/10 hover:bg-brand-gray-light focus:shadow-[0_0_0_2px] focus:shadow-black data-[placeholder]:text-violet9 outline-none"
        aria-label="Node topology"
      >
        <Select.Value
          placeholder={placeholder}
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
              {list.map((item, idx) => (
                  <Select.Item
                    key={idx}
                    value={item.value}
                    className="text-[13px] leading-none text-brand-text-dark flex items-center justify-between px-[15px] h-[35px] relative select-none data-[disabled]:text-green-300 data-[disabled]:pointer-events-none data-[highlighted]:outline-none data-[highlighted]:bg-brand-gray-medium data-[highlighted]:text-brand-text-light"
                  >
                    <Select.ItemText className="text-lg">
                      {item.name}
                    </Select.ItemText>
                    <Select.ItemIndicator className=" w-[25px] inline-flex items-center justify-center">
                      <CheckIcon />
                    </Select.ItemIndicator>
                  </Select.Item>
              ))}
            </Select.Group>
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
};

export default DefaultSelectBox;
