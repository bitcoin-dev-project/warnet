import React from 'react'
import { Pencil1Icon, TrashIcon, CopyIcon } from "@radix-ui/react-icons";
import { useNodeFlowContext } from '@/contexts/node-flow-context';
import { Node } from 'reactflow';
import { GraphNode } from '@/flowTypes';

const NodeList = () => {
  const { nodes, editNode, deleteNode, duplicateNode, nodeInfo } = useNodeFlowContext()

  const handleEditNode = (node: Node<GraphNode>) => {
    editNode(node)
  }
  const SingleNode = ({node}: {node: Node<GraphNode> }) => {
    const isSelected = nodeInfo?.id === node.id
    return (
      <div 
        data-node-highlight={isSelected || null} 
        className="group data-[node-highlight]:bg-brand-gray-medium data-[node-highlight]:text-white w-full text-xl flex justify-between items-center gap-2 px-4 py-4 border-b-[1px] border-brand-gray-medium"
      >
        <div className='flex h-full items-center gap-2'>
          <span className='w-3 h-3 rounded-full bg-red-300'></span>
          <p>{node?.data?.label}</p>
        </div>
        <div className='flex gap-2 text-black'>
          <button onClick={() => duplicateNode(node)} className='p-1 hover:text-brand-gray-light text-white'>
            <CopyIcon className='' />
          </button>
          <button onClick={() => handleEditNode(node)} className='p-1 hover:text-brand-gray-light text-white'>
            <Pencil1Icon />
          </button>
          <button onClick={() => deleteNode(node)} className='p-1 hover:text-brand-gray-light text-white'>
            <TrashIcon />
          </button>
        </div>
      </div>
    )
  }
  
  return (
    <div className="overflow-scroll flex flex-col">
      {nodes.map(node => <SingleNode key={node.id} node={node}/>)}
    </div>
  )
}

export default NodeList