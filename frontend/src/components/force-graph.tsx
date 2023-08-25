"use client";

import React, { useRef, useEffect } from "react";
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
  const tempLinkRef = useRef(null);

  useEffect(() => {
    const svg = d3.select(svgRef.current);
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
      .force("center", d3.forceCenter(CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2));

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
      .attr("stroke", "#fff")
      .attr("stroke-width", 1.5)
      .selectAll("rect")
      .data(nodes)
      .join("rect")
      .attr("width", 20)
      .attr("height", 20)
      .attr("fill", (d) => color(d.id!.toString()))
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

    const labels = svg
      .append("g")
      .selectAll("text")
      .data(nodes)
      .enter()
      .append("text")
      .attr("x", (d) => d.x!)
      .attr("y", (d) => d.y!)
      .text((d) => d.name!)
      .attr("font-size", "12px")
      .attr("font-weight", "bold")
      .attr("text-anchor", "middle")
      .attr("dy", -10);

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x!)
        .attr("y1", (d) => d.source.y!)
        .attr("x2", (d) => d.target.x!)
        .attr("y2", (d) => d.target.y!);

      node
        .attr("x", (d) => d.x! - NODE_ATTACHMENT_POINT)
        .attr("y", (d) => d.y! - NODE_ATTACHMENT_POINT);
      labels
        .attr("x", (d) => d.x! - NODE_ATTACHMENT_POINT)
        .attr("y", (d) => d.y! - NODE_ATTACHMENT_POINT);
    });

    // svg
    //   .append("line")
    //   .attr("ref", tempLinkRef.current)
    //   .attr("fill", "#153")
    //   .style("stroke", "#153")
    //   .style("stroke-dasharray", "5,5")
    //   .style("opacity", 0)
    //   .attr("width", "11.5");

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
      if (e.target.id === "canvas") {
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
      <svg
        id="canvas"
        ref={svgRef}
        width={CANVAS_WIDTH}
        height={CANVAS_HEIGHT}
        className={`bg-slate-100 border rounded-md`}
      ></svg>
    </>
  );
};

export default ForceGraph;
