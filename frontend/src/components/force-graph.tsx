"use client";

import React, { useRef, useEffect } from "react";
import * as d3 from "d3";
import { GraphData, GraphEdge, GraphNode } from "@/types";
import { CANVAS_HEIGHT, CANVAS_WIDTH, LINK_DISTANCE } from "@/config";

type ForceGraphProps = {
  setLinks: (link: any) => void;
} & GraphData;

const color = () => {
  const r = Math.floor(Math.random() * 255);
  const g = Math.floor(Math.random() * 255);
  const b = Math.floor(Math.random() * 255);

  return `rgb(${r}, ${g}, ${b})`;
};

const ForceGraph = ({ nodes, edges, setLinks }: ForceGraphProps) => {
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
      .alphaDecay(0.01);

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

    const link = svg
      .append("g")
      .attr("stroke", "#153")
      .attr("fill", "#159")
      .attr("stroke-width", "1.5")
      .attr("stroke-opacity", 1)
      .selectAll("line")
      .data(edges)
      .join("line");

    const node = svg
      .append("g")
      .attr("stroke", "#fff")
      .attr("stroke-width", 1.5)
      .selectAll("rect")
      .data(nodes)
      .join("rect")
      .attr("width", 20)
      .attr("height", 20)
      .attr("fill", "#153")
      .call(drag(simulation))
      .on("click", (event, d) => {
        if (selectedNode) {
          if (selectedNode !== d) {
            setLinks([...edges, { source: selectedNode.id, target: d.id }]);
          }
          setSelectedNode(null);
        } else {
          setSelectedNode(d);
        }
      });

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);

      node.attr("x", (d) => d.x - 10).attr("y", (d) => d.y - 10);
    });

    svg
      .append("line")
      .attr("ref", tempLinkRef.current)
      .style("stroke", "#153")
      .style("stroke-dasharray", "5,5")
      .style("opacity", 0)
      .attr("width", "11.5");

    function mouseMoved(event: any) {
      if (creatingLink) {
        const [x, y] = d3.pointer(event);
        d3.select(tempLinkRef.current)
          .attr("x1", creatingLink.source.x)
          .attr("y1", creatingLink.source.y)
          .attr("x2", x)
          .attr("y2", y)
          .style("opacity", 1);
      }
    }

    svg.on("mousemove", mouseMoved);
    svg.on("click", () => {
      console.log({ creatingLink });
      console.log({ nodes });
      console.log(tempLinkRef.current);
      if (creatingLink) {
        setCreatingLink(null);
        d3.select(tempLinkRef.current).style("opacity", 0);
      }
    });

    return () => {
      simulation.stop();
    };
  }, [nodes, edges, creatingLink, selectedNode, setLinks]);

  React.useEffect(() => {
    console.log("creatingLink", creatingLink);
  }, [creatingLink]);

  return (
    <svg
      ref={svgRef}
      width={CANVAS_WIDTH}
      height={CANVAS_HEIGHT}
      className="bg-slate-100 border rounded-md"
    ></svg>
  );
};

export default ForceGraph;
