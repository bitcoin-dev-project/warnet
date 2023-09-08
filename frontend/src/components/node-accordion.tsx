import classNames from "classnames";
import React from "react";
import getNodePeers from "@/helpers/get-node-peers";
import * as Accordion from "@radix-ui/react-accordion";
import { ChevronDownIcon } from "@radix-ui/react-icons";
import { useNodeFlowContext } from "@/contexts/node-flow-context";

type AccordionTriggerProps = React.ComponentProps<typeof Accordion.Trigger>;
type AccordionContentProps = React.ComponentProps<typeof Accordion.Content>;
type AccordionItemProps = React.ComponentProps<typeof Accordion.Item>;

const NodeAccordion = () => {
  const { nodes, edges, closeDialog, showGraphFunc } = useNodeFlowContext();

  return (
    <Accordion.Root
      className={`bg-mauve6 w-[300px] rounded-md shadow-[0_2px_10px] shadow-black/5 fixed right-[-100%] top-[-50%] bg-white p-5`}
      type="single"
      defaultValue="1"
      collapsible
    >
      <div className="fixed left-[50%] top-[35%] w-[100%] h-[1px] bg-white -z-10"></div>
      {nodes.map((node) => {
        return (
          <AccordionItem value={node?.id!.toString()} key={node.id}>
            <AccordionTrigger>
              {node?.data?.label + " " + `${node?.id! + 1}`}
            </AccordionTrigger>
            <AccordionContent>
              <div className="flex flex-col gap-y-1">
                <div className="flex justify-between">
                  <p className="text-sm text-black font-light mb-2">
                    core version
                  </p>
                  <p className="text-sm text-black font-light mb-2">
                    {node.data.version}
                  </p>
                </div>
                <div className="flex justify-between">
                  <p className="text-sm text-black font-light mb-2">latency</p>
                  <p className="text-sm text-black font-light mb-2">
                    {node.data.latency}
                  </p>
                </div>
                <div className="flex justify-between">
                  <p className="text-sm text-black font-light mb-2">base fee</p>
                  <p className="text-sm text-black font-light mb-2">
                    {node.data.baseFee}
                  </p>
                </div>
                <div className="flex justify-between">
                  <p className="text-sm text-black font-light mb-2">peers</p>
                  <p className="text-sm text-black font-light mb-2">
                    {getNodePeers(node?.id!, nodes, edges).length}
                  </p>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>
        );
      })}
      <div className="flex justify-end mt-4">
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
    </Accordion.Root>
  );
};

const AccordionItem: React.FC<AccordionItemProps> = React.forwardRef(
  ({ children, className, ...props }, forwardedRef) => (
    <Accordion.Item
      className={classNames(
        "focus-within:shadow-slate-50 mt-px overflow-hidden first:mt-0 first:rounded-t last:rounded-b focus-within:relative focus-within:z-10 focus-within:shadow-[0_0_0_2px]",
        className
      )}
      {...props}
      ref={forwardedRef}
    >
      {children}
    </Accordion.Item>
  )
);

const AccordionTrigger: React.FC<AccordionTriggerProps> = React.forwardRef(
  ({ children, className, ...props }, forwardedRef) => (
    <Accordion.Header className="flex">
      <Accordion.Trigger
        className={classNames(
          "text-black shadow-slate-50 hover:bg-mauve2 group flex h-[45px] flex-1 cursor-default items-center justify-between bg-white px-5 text-[15px] leading-none shadow-[0_1px_0] outline-none",
          className
        )}
        {...props}
        ref={forwardedRef}
      >
        {children}
        <ChevronDownIcon
          className="text-black ease-[cubic-bezier(0.87,_0,_0.13,_1)] transition-transform duration-300 group-data-[state=open]:rotate-180"
          aria-hidden
        />
      </Accordion.Trigger>
    </Accordion.Header>
  )
);

const AccordionContent: React.FC<AccordionContentProps> = React.forwardRef(
  ({ children, className, ...props }, forwardedRef) => (
    <Accordion.Content
      className={classNames(
        "text-mauve11 bg-mauve2 data-[state=open]:animate-slideDown data-[state=closed]:animate-slideUp overflow-hidden text-[15px]",
        className
      )}
      {...props}
      ref={forwardedRef}
    >
      <div className="py-[15px] px-5">{children}</div>
    </Accordion.Content>
  )
);

NodeAccordion.displayName = "AccordionDemo";
AccordionItem.displayName = "AccordionItem";
AccordionTrigger.displayName = "AccordionTrigger";
AccordionContent.displayName = "AccordionContent";

export default NodeAccordion;
