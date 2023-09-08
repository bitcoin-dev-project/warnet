"use client";

import React, { useRef, useEffect, useLayoutEffect } from "react";
import * as d3 from "d3";
import { GraphEdge, GraphNode } from "@/types";
import {
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
  LINK_DISTANCE,
  NODE_ATTACHMENT_POINT,
} from "@/config";
import { useNodeGraphContext } from "@/contexts/node-graph-context";
import Sidebar from "./sidebar";
import NodeInfo from "./node-info-dialog";

const color = () => {
  const r = Math.floor(Math.random() * 255);
  const g = Math.floor(Math.random() * 255);
  const b = Math.floor(Math.random() * 255);

  return `rgb(${r}, ${g}, ${b})`;
};

const ForceGraph = () => {
  const { edges, nodes, setNodeEdges, isDialogOpen, showGraph } =
    useNodeGraphContext();
  const [selectedNode, setSelectedNode] = React.useState<GraphNode | null>(
    null
  );
  const [creatingLink, setCreatingLink] = React.useState<GraphEdge | null>(
    null
  );

  const svgRef = useRef(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const tempLinkRef = useRef(null);

  useEffect(() => {
    const svg = d3.select(svgRef.current);

    const canvas = canvasRef.current
    const canvasDetails = {
      height: canvas?.clientHeight ?? CANVAS_HEIGHT,
      width: canvas?.clientWidth ?? CANVAS_WIDTH
    }

    // const zoom = d3.zoom()
    //   .scaleExtent([0.5, 10]) // Adjust zoom limits as needed
    //   .on("zoom", zoomed);
    // svg.call(zoom);
    // function zoomed(event) {
    //   svg.attr("transform", event.transform);
    // }

    svg.selectAll("*").remove();
    const simulation: d3.Simulation<GraphNode, undefined> = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3
          .forceLink(edges)
          .id((d) => d?.index || 0)
          .distance(LINK_DISTANCE)
      )
      .force("charge", d3.forceManyBody().strength(-5))
      .alphaDecay(0.01)
      .force("center", d3.forceCenter(canvasDetails.width / 2, canvasDetails.height / 2));
    const drag = (simulation: d3.Simulation<GraphNode, undefined>) => {
      function dragstarted(event: any) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        event.subject.fx = event.subject.x;
        event.subject.fy = event.subject.y;
      }

      function dragged(event: any) {
        event.subject.fx = event.x;
        event.subject.fy = event.y;
      }

      function dragended(event: any) {
        if (!event.active) simulation.alphaTarget(0);
        event.subject.fx = null;
        event.subject.fy = null;
      }

      return d3
        .drag()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended);
    };

    const color = d3.scaleOrdinal(d3.schemeCategory10);

    const link = svg
      .append("g")
      .attr("stroke", "#153")
      .attr("fill", "#159")
      .attr("stroke-width", "1.5")
      .attr("stroke-opacity", 1)
      .selectAll("line")
      .data(edges)
      .enter()
      .append("line");

    const node = svg
      .append("g")
      .selectAll(".node")
      .data(nodes)
      .join("svg")
      .html((d) => `
        <svg width="187" height="64" viewBox="0 0 187 64" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect width="12" height="64" rx="6" fill="#0F62FE"/>
          <rect x="12.5" y="7.5" width="162" height="49" fill="black"/>
          <circle cx="36" cy="32" r="8" fill="#FF02A9"/>
          <text x="50" y="37" class="cursor-pointer text-sm fill-white">${d.name}</text>
          <rect x="12.5" y="7.5" width="162" height="49" stroke="#545454"/>
          <rect x="175" width="12" height="64" rx="6" fill="#0F62FE"/>
        </svg>
      `)
      .classed("node", true)
      // .append("svg")
      .call(drag(simulation))
      .on("click", (event, d) => {
        if (selectedNode) {
          if (selectedNode !== d) {
            // setLinks([...edges, { source: selectedNode.id, target: d.id }]);
            setNodeEdges([
              ...edges,
              {
                source: selectedNode.id,
                target: d.id,
                // id: 1,
              },
            ]);
          }
          setSelectedNode(null);
        } else {
          setSelectedNode(d);
        }
      });

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x!)
        .attr("y1", (d) => d.source.y!)
        .attr("x2", (d) => d.target.x!)
        .attr("y2", (d) => d.target.y!);

      node
        .attr("x", (d) => d.x! - NODE_ATTACHMENT_POINT)
        .attr("y", (d) => d.y! - NODE_ATTACHMENT_POINT);
    });

    function mouseMoved(event: any) {
      if (creatingLink) {
        const [x, y] = d3.pointer(event);
        d3.select(tempLinkRef.current)
          .attr("x1", creatingLink.source.x!)
          .attr("y1", creatingLink.source.y!)
          .attr("x2", x)
          .attr("y2", y)
          .style("opacity", 1);
      }
    }

    svg.on("mousemove", mouseMoved);
    svg.on("click", (e, d) => {
      if (e.target.id === "svg-container") {
        setSelectedNode(null);
      }
      // if (creatingLink) {
      //   setCreatingLink(null);
      //   // d3.select(tempLinkRef.current).style("opacity", 0);
      // }
    });

    return () => {
      simulation.stop();
      svg.on("click", null);
      node.on("click", null);
    };
  }, [nodes, edges, creatingLink, selectedNode, setNodeEdges]);

  useEffect(() => {
    console.log({ nodes });
  }, [nodes]);
  useEffect(() => {
    console.log({ edges });
  }, [edges]);
  useEffect(() => {
    console.log(selectedNode);
  }, [selectedNode]);

  if (!showGraph) {
    return null;
  }

  return (
    <>
      <Sidebar />
      {isDialogOpen && <NodeInfo />}
      <div id="canvas" ref={canvasRef} className="w-full h-full bg-brand-gray-medium border">
        <svg
          id="svg-container"
          ref={svgRef}
          // width={CANVAS_WIDTH}
          // height={CANVAS_HEIGHT}
          className="w-full h-full"
        ></svg>
      </div>
    </>
  );
};

export default ForceGraph;
