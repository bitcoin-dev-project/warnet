
const graphmlDIR = "graphml"
const downloadGraph = async (path: string) => {
  console.log({path})
  const a = document.createElement("a");
  a.href = `${graphmlDIR}/${path}`;
  a.download = path;
  a.click();
}

export default downloadGraph