import { BITCOIN_CORE_BINARY_VERSIONS } from "@/config";
import React, { FC } from "react";

type SidebarProps = {
  onAddNode: (node: any) => void;
};

const Sidebar: FC<SidebarProps> = ({ onAddNode }) => {
  return (
    <aside className="flex flex-col items-center justify-center w-2/6 min-h-screen px-4">
      <section className="flex flex-col p-4 w-full h-96 rounded-xl shadow-md border mx-auto text-black">
        <p className="text-sm font-light mb-2">Add node</p>
        <div className="flex gap-4">
          {BITCOIN_CORE_BINARY_VERSIONS.map((version, index) => (
            <button
              key={`${index}-${version}`}
              className="text-[12px] border rounded-md px-2 py-1"
              onClick={() => onAddNode(version)}
            >
              {version}
            </button>
          ))}
          {/* <button
            className="text-[12px] border rounded-md px-2 py-1"
            onClick={onAddNode}
          >
            24.0
          </button> */}
        </div>
      </section>
    </aside>
  );
};

export default Sidebar;
