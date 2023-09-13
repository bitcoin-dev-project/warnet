"use client";

import * as Tabs from "@radix-ui/react-tabs";

function Dashboard() {
    // TODO: make this a bit more dynamic
    // fetch the list of dashboards and their URLs from the server
  return (
    <Tabs.Root defaultValue="prometheus" className={`flex flex-col space-y-4`}>
      <Tabs.List className="flex gap-x-4 px-10 pt-6" aria-label="Dashboard tabs">
        <Tabs.Trigger
          value="prometheus"
          className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 focus:outline-none"
        >
          Prometheus
        </Tabs.Trigger>
        <Tabs.Trigger
          value="forkObserver"
          className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 focus:outline-none"
        >
          Fork Observer
        </Tabs.Trigger>
      </Tabs.List>

      <div className="flex-1 p-5 px-10">
        <Tabs.Content value="prometheus">
          <iframe
            className={`rounded shadow-lg w-full h-screen`}
            src="http://localhost:9090/graph"
          />
        </Tabs.Content>

        <Tabs.Content value="forkObserver">
          <iframe
            className="rounded shadow-lg w-full h-screen"
            src="http://localhost:12323/"
          ></iframe>
        </Tabs.Content>
      </div>
    </Tabs.Root>
  );
}

export default Dashboard;
