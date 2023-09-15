import { GRAPHML_DIR } from "@/config"
import { GraphEdge, GraphNode, NodePersona } from "@/flowTypes"
// import * as fs from "fs"
import { Edge, Node } from "reactflow"
import * as xml2js from "xml2js"

const parser = new xml2js.Parser()

export const readXML = async (path: string, configObj?: Partial<NodePersona>) : Promise<Partial<NodePersona>>  => {
  try {
    let file
    const nodes: Node<GraphNode>[] = []
    const edges: Edge<GraphEdge>[] = []
    const mapping = {} as any
    // const file = fs.readFileSync("/Users/topgamer/Desktop/dev/warnet/frontend/public/graphml/wheel_graph_n100_pos.graphml")
  
    if (window) {
      const response = await fetch(GRAPHML_DIR + "/" + path);
      if (!response.ok) {
        console.log("something went wrong")
        throw new Error('Failed to fetch the XML file');
      }

      file = await response.text();
    } else {
      throw new Error("cannot run on server")
    }
  
    parser.parseString(file, function (err, result) {
      for (const key of result.graphml.key) {
        const id = key.$.id as string
        mapping[id] = key.$?.["attr.name"]
      }
      
      for (const node of result.graphml.graph[0].node) {
        const singleNode = {
          type: "draggable"
        } as any
        const id = node.$.id as string
        singleNode.id = id
  
        if (node.data?.length) {
          for (const data of node.data) {
            if (!singleNode.data) {
              singleNode.data = {}
            }

            const value = data["_"]
            const mappedLabel = mapping[data?.$?.key]
  
            singleNode.data[mappedLabel] = value
  
            if (mappedLabel === "x" || mappedLabel === "y") {
              if (!singleNode.position) singleNode.position = {}
              singleNode.position[mappedLabel] = Number(value) ?? null
            } else {
              singleNode.position = {
                x: 0,
                y: 0
              }
            }
          }
        }
        nodes.push(singleNode)
      }
      
      for (const edge of result.graphml.graph[0].edge) {
        let singleEdge = {} as any
        const {id, source, target} = edge.$
        singleEdge = {
          id, source, target
        }
  
        edges.push(singleEdge)
      }
  
      // console.log(JSON.stringify(nodes.slice(0, 2)))
      // console.log(JSON.stringify(edges.slice(0, 2)))
    })
  
    return {nodes, edges, ...configObj}
  } catch (err) {
    console.error(err)
    return {}
  }
} 
