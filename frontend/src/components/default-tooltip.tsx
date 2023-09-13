import * as Tooltip from "@radix-ui/react-tooltip";
import React, { FC } from "react";

interface IDefaultTooltip {
  children: React.ReactNode;
  content: any
}
const DefaultTooltip: FC<IDefaultTooltip> = ({ children, content}) => {
  return (
    <Tooltip.Provider>
      <Tooltip.Root>
        <Tooltip.Trigger>{children}</Tooltip.Trigger>
        <Tooltip.Portal >
          <Tooltip.Content >
            {content}
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
};

export default DefaultTooltip;
