import { GraphNode } from "@/flowTypes";
import { useCallback } from "react";
import { Handle, Position } from "reactflow";

interface IDraggableNode {
  data: GraphNode;
  isConnectable: boolean;
}
function DraggableNode({ data, isConnectable }: IDraggableNode) {
  const nodeStyling = {
    background: "#0F62FE",
    minHeight: "64px",
    border: "1px solid #0F62FE",
    width:"11px",
    borderRadius:"11px"
  };
  return (
    <div >
      <Handle
        type="target"
        position={Position.Left}
        style={nodeStyling}
        isConnectable={isConnectable}
      />
      <div title={data?.name} className="flex bg-black border items-center gap-x-3 border-[#545454] px-4 py-3.5 font-ibm max-w-[225px] w-full">
        <div className="min-w-[16px] max-w-[16px] rounded-full min-h-[16px] max-h-[16px]" style={{background:"#FF0202"}}/>
        <label htmlFor="text" className="first-letter:uppercase max-w-[100%] whitespace-nowrap text-ellipsis overflow-hidden text-xl leading-5">
          {data?.name}
        </label>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        id="a"
        isConnectable={isConnectable}
        style={nodeStyling}
        className="bg-[#0F62FE] min-h-[64px]"
      />
    </div>
  );
}

export default DraggableNode;
