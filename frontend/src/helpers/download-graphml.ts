import { GRAPHML_DIR } from "@/config";

const downloadGraph = async (path: string) => {
  try {
    const response = await fetch(GRAPHML_DIR + "/" + path);
    if (!response.ok) {
      throw new Error('Failed to fetch the XML file');
    }
    const xml = await response.text();
    const blob = new Blob([xml], { type: "application/xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = path;
    a.click();
  } catch(error) {
    console.error(error)
  }
}

export default downloadGraph