import React from 'react'
import { useNodeGraphContext } from '@/contexts/node-graph-context'
import { GraphNode } from '@/types'
import { Pencil1Icon, TrashIcon, CopyIcon } from "@radix-ui/react-icons";

const NodeList = () => {
  const {closeDialog, nodes, editNode, deleteNode, duplicateNode } = useNodeGraphContext()
  const handleEditNode = (node: GraphNode) => {
    editNode(node)
  }
  const SingleNode = ({node}: {node: GraphNode}) => {
    return (
      <div className='w-full text-xl flex justify-between items-center gap-2 px-4 py-4 border-b-[1px] border-brand-gray-medium'>
        <div className='flex h-full items-center gap-2'>
          <span className='w-3 h-3 rounded-full bg-red-300'></span>
          <p>{node.name}</p>
        </div>
        <div className='flex gap-2 text-white'>
          <button onClick={() => duplicateNode(node)} className='p-1 hover:text-brand-gray-light'>
            <CopyIcon className='' />
          </button>
          <button onClick={() => handleEditNode(node)} className='p-1 hover:text-brand-gray-light'>
            <Pencil1Icon />
          </button>
          <button onClick={() => deleteNode(node)} className='p-1 hover:text-brand-gray-light'>
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