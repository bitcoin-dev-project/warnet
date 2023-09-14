import * as fs from "fs"
import * as xml2js from "xml2js"

const parser = new xml2js.Parser()

export const readXML = () => {
  const file = fs.readFileSync("/Users/topgamer/Desktop/dev/warnet/frontend/src/assests/graphml/random_geometric-graph_n100_r0.2.graphml")
  parser.parseString(file, function (err, result) {
    console.dir(result);
    console.log('Done');
  })
} 
