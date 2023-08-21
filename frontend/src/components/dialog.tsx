"use client";

import React from "react";

import { useNodeGraphContext } from "@/contexts/node-graph-context";
import * as Dialog from "@radix-ui/react-dialog";
import { Cross2Icon } from "@radix-ui/react-icons";

import NodeAccordion from "./node-accordion";
import SelectBox from "./select";

const DialogBox = () => {
  const {
    isDialogOpen,
    closeDialog,
    openDialog,
    showGraphFunc,
    showNodePersonaInfo,
    steps,
    nodePersonaType,
  } = useNodeGraphContext();

  const dialogContentStyles = () => {
    switch (steps) {
      case -1:
        return "top-[50%] left-[50%] translate-x-[-50%] translate-y-[-50%]";
      case 1:
        return "top-[50%] left-[35%] translate-x-[-50%] translate-y-[-50%]";
      default:
        return null;
    }
  };

  const handleNextFunction = () => {
    if (nodePersonaType === "prebuilt") {
      showNodePersonaInfo();
    }
    if (nodePersonaType === "custom") {
      closeDialog();
      showGraphFunc();
    }
  };

  return (
    <Dialog.Root open={isDialogOpen}>
      <Dialog.Trigger asChild onClick={openDialog}>
        <button
          className={`${
            steps !== -1 && "hidden"
          } text-black shadow-blackA7 hover:bg-mauve3 inline-flex h-[35px] items-center justify-center rounded-[4px] bg-white px-[15px] font-medium leading-none shadow-[0_2px_10px] focus:shadow-[0_0_0_2px] focus:shadow-black focus:outline-none`}
        >
          Build your node profile
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="bg-slate-50 opacity-10 data-[state=open]:animate-overlayShow fixed inset-0" />
        <Dialog.Content
          className={`${dialogContentStyles()} data-[state=open]:animate-contentShow flex flex-col justify-center fixed max-h-[85vh] w-[90vw] max-w-[450px] rounded-[6px] bg-white p-[25px] shadow-[hsl(206_22%_7%_/_35%)_0px_10px_38px_-10px,_hsl(206_22%_7%_/_20%)_0px_10px_20px_-15px] focus:outline-none`}
        >
          <Dialog.Title className="text-black m-0 text-[17px] font-medium">
            Node profile
          </Dialog.Title>
          <Dialog.Description className="text-black mt-[10px] mb-5 text-[15px] leading-normal">
            You can choose your profile here.
          </Dialog.Description>
          <SelectBox />
          <div className="mt-[25px] flex justify-end">
            <Dialog.Close asChild>
              <button
                onClick={handleNextFunction}
                disabled={!nodePersonaType}
                className={`${
                  steps === 1 && "hidden"
                } disabled:bg-slate-100 disabled:text-slate-400 bg-green-100 text-green-700 hover:bg-green5 focus:shadow-green7 inline-flex h-[35px] items-center justify-center rounded-[4px] px-[15px] font-medium leading-none focus:shadow-[0_0_0_2px] focus:outline-none`}
              >
                Next
              </button>
            </Dialog.Close>
          </div>
          <Dialog.Close asChild>
            <button
              onClick={closeDialog}
              className="text-black hover:bg-violet-100 focus:shadow-violet7 absolute top-[10px] right-[10px] inline-flex h-[25px] w-[25px] appearance-none items-center justify-center rounded-full focus:shadow-[0_0_0_2px] focus:outline-none"
              aria-label="Close"
            >
              <Cross2Icon />
            </button>
          </Dialog.Close>
          {nodePersonaType === "prebuilt" && steps === 1 && <NodeAccordion />}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};

export default DialogBox;
