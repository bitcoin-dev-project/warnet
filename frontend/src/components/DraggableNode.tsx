import { useNodeFlowContext } from "@/contexts/node-flow-context";
import { GraphNode } from "@/flowTypes";
import { Handle, Position } from "reactflow";

interface IDraggableNode {
  data: GraphNode;
  isConnectable: boolean;
}
function DraggableNode({ data, isConnectable }: IDraggableNode) {
  const { nodeInfo } = useNodeFlowContext();
  const isSelected = nodeInfo?.id === data.id

  const nodeStyling = {
    background: "#0F62FE",
    minHeight: "64px",
    border: `${isSelected ? "2px solid white" : "1px solid #0F62FE"}`,
    width:"11px",
    borderRadius:"11px"
  };
  return (
    <div 
      data-node-highlight={isSelected || null} 
      className="group data-[node-highlight]:shadow-[0_0_10px_rgba(255,255,255,0.3)]"
    >
      <Handle
        type="target"
        position={Position.Left}
        style={nodeStyling}
        isConnectable={isConnectable}
      />
      <div id={data.id} title={data?.label} className="flex bg-black border group-data-[node-highlight]:bg-brand-gray-dark group-data-[node-highlight]:border-white group-data-[node-highlight]:border-2 items-center gap-x-3 border-[#545454] px-4 py-3.5 font-ibm max-w-[225px] w-full">
        <div className="min-w-[16px] max-w-[16px] rounded-full min-h-[16px] max-h-[16px] bg-[#FF0202]"/>
        <label htmlFor="text" className="first-letter:uppercase max-w-[100%] whitespace-nowrap text-ellipsis overflow-hidden text-xl leading-5 pointer-events-none">
          {data?.label}
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
